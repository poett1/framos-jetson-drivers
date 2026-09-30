"""Kernel log: CSI, PHY and RCE capture errors."""

import re
import subprocess

CSI_ERROR_RE = re.compile(r"uncorr_err|corr_err|err_rec|PHY_INTR|CIL_INTR|CSIMUX|"
                          r"discarding frame|request timed out|nvcsi.*err", re.I)


def kernel_log():
    return subprocess.run(["dmesg"], capture_output=True, text=True).stdout.splitlines()


def new_errors(before, after):
    """CSI errors logged in `after` since `before` was taken; copes with a wrapped ring buffer."""
    if after[:len(before)] == before:
        new = after[len(before):]
    elif before and before[-1] in after:
        new = after[len(after) - after[::-1].index(before[-1]):]
    else:
        new = after
    return [line for line in new if CSI_ERROR_RE.search(line)]
