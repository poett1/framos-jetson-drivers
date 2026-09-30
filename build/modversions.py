#!/usr/bin/env python3
#
# Checks, before installing, that the rebuilt camera stack fits the stock modules
# (CONFIG_MODVERSIONS): every symbol an installed module imports from a module that
# stays stock must have the stock CRC, and no stock module may depend on a module
# that gets replaced. Used by target_build.sh install_oot_modules.
#
# The __versions section of 6.8 modules has variable-length entries
# (u32 entry size, u32 CRC, NUL-padded name), which "modprobe --dump-modversions"
# cannot read.

import argparse
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def modname(path_or_name):
    """Module name as the kernel uses it: basename without .ko*, '-' -> '_'."""
    name = os.path.basename(str(path_or_name))
    name = name.split(".ko")[0]
    return name.replace("-", "_")


def parse_versions(blob):
    """Parse a __versions section: {symbol: crc}."""
    versions = {}
    pos = 0
    while pos + 8 <= len(blob):
        size, crc = struct.unpack_from("<II", blob, pos)
        if size < 8:
            break
        name = blob[pos + 8:pos + size].split(b"\0", 1)[0].decode()
        versions[name] = crc
        pos += size
    return versions


def parse_symvers(path):
    """Parse a Module.symvers: {symbol: (crc, module name)}."""
    symvers = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            symvers[fields[1]] = (int(fields[0], 16), modname(fields[2]))
    return symvers


def check_imports(imports, installed, ours, stock):
    """imports: {module: {symbol: crc}}; installed: names being installed;
    ours/stock: symvers maps. Returns a list of problems."""
    problems = []
    for module, syms in sorted(imports.items()):
        for sym, crc in sorted(syms.items()):
            exporter = (ours.get(sym) or stock.get(sym) or (None, None))[1]
            if exporter is None:
                problems.append(f"{module}: {sym} is exported by no module")
            elif exporter in installed:
                continue
            elif sym in stock and stock[sym][0] != crc:
                problems.append(f"{module}: {sym} has CRC 0x{crc:08x}, "
                                f"stock {stock[sym][1]} exports 0x{stock[sym][0]:08x}")
    return problems


def check_reverse_deps(stock_deps, installed):
    """stock_deps: {stock module: [dependencies]}. Returns a list of problems."""
    return [f"stock {module} depends on replaced {dep}"
            for module, deps in sorted(stock_deps.items()) if module not in installed
            for dep in deps if dep in installed]


def _read_versions(ko):
    with tempfile.NamedTemporaryFile() as tmp:
        subprocess.run(["objcopy", "-O", "binary", "--only-section=__versions",
                        str(ko), tmp.name], check=True)
        return parse_versions(Path(tmp.name).read_bytes())


def _stock_deps(modules_dir, exclude_dir):
    deps = {}
    for ko in Path(modules_dir).rglob("*.ko*"):
        if exclude_dir and Path(exclude_dir) in ko.parents:
            continue
        out = subprocess.run(["modinfo", "-F", "depends", str(ko)],
                             capture_output=True, text=True).stdout.strip()
        deps[modname(ko)] = [modname(d) for d in out.split(",") if d]
    return deps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", nargs="+", required=True, help=".ko files to install")
    ap.add_argument("--our-symvers", nargs="+", required=True)
    ap.add_argument("--stock-symvers", nargs="+", required=True)
    ap.add_argument("--stock-modules-dir", required=True)
    ap.add_argument("--exclude-dir", help="our own install dir inside the stock dir")
    args = ap.parse_args()

    installed = {modname(ko) for ko in args.install}
    ours, stock = {}, {}
    for f in args.our_symvers:
        ours.update(parse_symvers(f))
    for f in args.stock_symvers:
        stock.update(parse_symvers(f))
    imports = {modname(ko): _read_versions(ko) for ko in args.install}

    problems = check_imports(imports, installed, ours, stock)
    problems += check_reverse_deps(_stock_deps(args.stock_modules_dir, args.exclude_dir),
                                   installed)
    for p in problems:
        print(p)
    print(f"{len(installed)} modules checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
