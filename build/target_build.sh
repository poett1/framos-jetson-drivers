#!/bin/bash

# This script builds and installs, on the Jetson itself (stock Jetpack 7.2.1):
# out-of-tree kernel modules & device tree overlays
#
# Usage: source target_build.sh, then run one of the printed commands.


# color output
red=$'\e[31m'
grn=$'\e[32m'
yel=$'\e[33m'
blu=$'\e[34m'
mag=$'\e[35m'
cyn=$'\e[36m'
normal=$'\e[0m'


# export env
_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export L4T_SOURCE=${L4T_SOURCE:-$(cd "${_script_dir}/../source" && pwd)}
export KERNEL_RELEASE=${KERNEL_RELEASE:-$(uname -r)}


# check kernel headers and build tools
function _preflight() {
    if [ "${KERNEL_RELEASE}" != "$(uname -r)" ]; then
        echo -e "${red}modules would be built for ${KERNEL_RELEASE} but the running kernel is $(uname -r)${normal}"
        return 1
    fi
    if [ ! -d "/lib/modules/${KERNEL_RELEASE}/build" ]; then
        echo -e "${red}kernel headers /lib/modules/${KERNEL_RELEASE}/build not found; install nvidia-l4t-kernel-headers${normal}"
        return 1
    fi
    local tool
    for tool in make gcc cpp dtc; do
        if ! command -v ${tool} &> /dev/null; then
            echo -e "${red}${tool} not found; install build-essential and device-tree-compiler${normal}"
            return 1
        fi
    done
}

# Errors are passed on with "|| return 1" rather than "set -e": bash ignores
# set -e inside functions called from "&&", "||" or "if", as in
# "check && install_all".

# build out-of-tree kernel modules
function build_oot_modules() {
    _preflight || return 1
    echo ; echo; echo -e "${yel}start out of tree kernel modules build ... ${normal}"
    make -C ${L4T_SOURCE} modules KERNEL_HEADERS=/lib/modules/${KERNEL_RELEASE}/build || return 1
    _write_build_stamp || return 1
}

# build FRAMOS device tree overlays
function build_dtree() {(
    set -o pipefail
    overlay_dir=${L4T_SOURCE}/hardware/nvidia/t23x/nv-public/overlay
    out_dir=${L4T_SOURCE}/out/dtbo
    inc=""
    for dir in ${L4T_SOURCE}/hardware/nvidia/*/nv-public/include/*; do
        [ -d "${dir}" ] && inc="${inc} -I ${dir}"
    done
    echo ; echo; echo -e "${yel}start device tree overlays build ... ${normal}"
    mkdir -p ${out_dir} || exit 1
    for dts in ${overlay_dir}/*fr_*-overlay.dts; do
        name=$(basename ${dts} .dts)
        if ! cpp -nostdinc -undef -x assembler-with-cpp -D__DTS__ ${inc} ${dts} \
                | dtc -@ -q -I dts -O dtb -o ${out_dir}/${name}.dtbo -; then
            echo -e "${red}overlay ${name} failed to build${normal}"
            exit 1
        fi
    done
    echo -e "${grn}$(ls ${out_dir}/*.dtbo | wc -l) overlays in ${out_dir}${normal}"
)}

# build DTBs & out-of-tree kernel modules
function build_all() {
    build_dtree || return 1
    build_oot_modules || return 1
}

# check the build environment and build everything without installing
function check() {
    _preflight || return 1
    build_all || return 1
    echo
    echo -e "${grn}$(find ${L4T_SOURCE}/nvidia-oot -name '*.ko' | wc -l) modules" \
        "($(find ${L4T_SOURCE}/nvidia-oot -name 'fr_*.ko' | wc -l) fr_*)," \
        "$(ls ${L4T_SOURCE}/out/dtbo/*.dtbo | wc -l) overlays${normal}"
}


export MODULES_DIR=${MODULES_DIR:-/lib/modules/${KERNEL_RELEASE}}
export FRAMOS_MODULES_DIR=${FRAMOS_MODULES_DIR:-${MODULES_DIR}/updates/framos}
export FRAMOS_DEPMOD_CONF=${FRAMOS_DEPMOD_CONF:-/etc/depmod.d/framos.conf}
export FRAMOS_DTBO_DIR=/boot/framos/dtbo
# the stock symbol versions a build is made against; their checksums are the build stamp
export STOCK_SYMVERS=${STOCK_SYMVERS:-"${MODULES_DIR}/build/Module.symvers $(ls /usr/src/nvidia/*/Module.symvers 2> /dev/null | tr '\n' ' ')"}
export BUILD_STAMP=${BUILD_STAMP:-${L4T_SOURCE}/out/build-stamp}

# record which kernel headers the modules were built against
function _write_build_stamp() {
    mkdir -p "$(dirname ${BUILD_STAMP})" || return 1
    sha256sum ${STOCK_SYMVERS} > ${BUILD_STAMP} || return 1
}

# refuse modules built against other headers (an updated nvidia-l4t-kernel* package
# often keeps the same "uname -r")
function _check_build_stamp() {
    if [ ! -f "${BUILD_STAMP}" ]; then
        echo -e "${red}no build stamp ${BUILD_STAMP}: run check first${normal}"
        return 1
    fi
    if ! sha256sum --status -c ${BUILD_STAMP} 2> /dev/null; then
        echo -e "${red}the modules were built against other kernel headers than the installed ones: run check again${normal}"
        return 1
    fi
}

# refuse modules built for another kernel release
function _check_vermagic() {
    local ko vermagic
    for ko in "$@"; do
        vermagic=$(modinfo -F vermagic ${ko} | cut -d" " -f1)
        if [ "${vermagic}" != "${KERNEL_RELEASE}" ]; then
            echo -e "${red}$(basename ${ko}) was built for ${vermagic}, the kernel is ${KERNEL_RELEASE}: run check again${normal}"
            return 1
        fi
    done
}

# print the built modules to install: fr_*, tegra-camera, and every built module
# that depends on one of them, directly or indirectly (the camera-core changes
# alter symbol CRCs, CONFIG_MODVERSIONS)
function _camera_stack() {
    local -A path=() deps=() selected=()
    local ko name changed=1
    while read -r ko; do
        name=$(basename ${ko} .ko | tr - _)
        path[${name}]=${ko}
        deps[${name}]=" $(modinfo -F depends ${ko} | tr - _ | tr , ' ') "
        [[ ${name} == fr_* || ${name} == tegra_camera ]] && selected[${name}]=1
    done < <(find ${L4T_SOURCE}/nvidia-oot ${L4T_SOURCE}/hwpm -name '*.ko')
    while [ ${changed} = 1 ]; do
        changed=0
        for name in "${!path[@]}"; do
            [ -n "${selected[${name}]}" ] && continue
            for dep in ${deps[${name}]}; do
                if [ -n "${selected[${dep}]}" ]; then
                    selected[${name}]=1
                    changed=1
                    break
                fi
            done
        done
    done
    # modules the stock install does not ship are left out, except fr_*
    for name in "${!selected[@]}"; do
        if [[ ${name} == fr_* ]] || modinfo -k ${KERNEL_RELEASE} -n ${name} &> /dev/null; then
            echo ${path[${name}]}
        fi
    done | sort
}

# depmod override lines for the given .ko files; kmod matches an override against
# the file name, so "tegra-camera", not the module name "tegra_camera"
function _override_lines() {
    local ko
    for ko in "$@"; do
        echo "override $(basename ${ko} .ko) * updates/framos"
    done
}

# copy the modules into updates/framos, write the overrides, run depmod and check that
# every module resolves there; on any failure remove it all again (stock modules apply)
function _install_files() {
    sudo rm -rf ${FRAMOS_MODULES_DIR} || return 1
    if ! { sudo mkdir -p ${FRAMOS_MODULES_DIR} && sudo cp "$@" ${FRAMOS_MODULES_DIR}/ &&
            { echo "# FRAMOS camera stack, written by build/target_build.sh install_oot_modules"
              _override_lines "$@"; } | sudo tee ${FRAMOS_DEPMOD_CONF} > /dev/null &&
            sudo depmod -a ${KERNEL_RELEASE} && _verify_install "$@"; }; then
        _rollback_install
        return 1
    fi
}

function _verify_install() {
    local ko name
    for ko in "$@"; do
        name=$(modinfo -F name ${ko})
        if [[ -z "${name}" || "$(modinfo -k ${KERNEL_RELEASE} -n ${name} 2> /dev/null)" != ${FRAMOS_MODULES_DIR}/* ]]; then
            echo -e "${red}$(basename ${ko}) does not resolve to ${FRAMOS_MODULES_DIR}${normal}"
            return 1
        fi
    done
    sudo modprobe --dry-run -S ${KERNEL_RELEASE} fr_imx900 || return 1
}

function _rollback_install() {
    sudo rm -rf ${FRAMOS_MODULES_DIR} ${FRAMOS_DEPMOD_CONF}
    sudo depmod -a ${KERNEL_RELEASE}
    echo -e "${red}install failed and was rolled back: the stock modules are used${normal}"
}

# install the camera stack into updates/framos, overriding the stock modules
function install_oot_modules() {
    _preflight || return 1
    local modules=($(_camera_stack)) ko name
    if [ ${#modules[@]} = 0 ]; then
        echo -e "${red}no built modules found; run build_oot_modules first${normal}"
        return 1
    fi
    _check_build_stamp || return 1
    _check_vermagic "${modules[@]}" || return 1
    echo ; echo; echo -e "${yel}checking ${#modules[@]} modules against the stock modules ... ${normal}"
    python3 ${_script_dir}/modversions.py --install "${modules[@]}" \
        --our-symvers ${L4T_SOURCE}/nvidia-oot/Module.symvers ${L4T_SOURCE}/hwpm/drivers/tegra/hwpm/Module.symvers \
        --stock-symvers ${MODULES_DIR}/build/Module.symvers /usr/src/nvidia/*/Module.symvers \
        --stock-modules-dir ${MODULES_DIR}/updates --exclude-dir ${FRAMOS_MODULES_DIR} || return 1

    echo -e "${yel}out of tree kernel modules install ... ${normal}"
    _install_files "${modules[@]}" || return 1
    echo -e "${grn}${#modules[@]} modules installed in ${FRAMOS_MODULES_DIR}; reboot to load them${normal}"
}

# install the FRAMOS overlays
function install_dtree() {
    echo ; echo; echo -e "${yel}device tree overlays install ... ${normal}"
    sudo mkdir -p ${FRAMOS_DTBO_DIR} || return 1
    sudo cp ${L4T_SOURCE}/out/dtbo/*.dtbo ${FRAMOS_DTBO_DIR}/ || return 1
}

# install DTBs & out-of-tree kernel modules
function install_all() {
    install_dtree || return 1
    install_oot_modules || return 1
}

# remove the FRAMOS modules, overlays and boot entry; the stock setup is used again
function uninstall() {
    sudo python3 ${_script_dir}/../tools/framos_jetsonio.py remove-boot-entry /boot/extlinux/extlinux.conf || return 1
    sudo rm -rf ${FRAMOS_MODULES_DIR} ${FRAMOS_DEPMOD_CONF} ${FRAMOS_DTBO_DIR} || return 1
    sudo depmod -a ${KERNEL_RELEASE} || return 1
    echo -e "${grn}FRAMOS modules, overlays and the FramosCamera boot entry removed; reboot to use the stock setup.${normal}"
}


echo; echo; echo -e "${grn}L4T_SOURCE = ${L4T_SOURCE}"
echo -e "${grn}KERNEL_RELEASE = ${KERNEL_RELEASE}"


echo; echo "${cyn}C O M M A N D S:"
echo -e "${red}build_dtree${normal}:	\t\tbuild device tree overlays"
echo -e "${red}build_oot_modules${normal}:\t\tbuild out-of-tree kernel modules"
echo -e "${red}build_all${normal}:	\t\tbuild all"
echo -e "${red}install_dtree${normal}:	\t\tinstall device tree overlays to ${FRAMOS_DTBO_DIR}"
echo -e "${red}install_oot_modules${normal}:\t\tinstall the camera stack to ${FRAMOS_MODULES_DIR}"
echo -e "${red}install_all${normal}:	\t\tinstall all"
echo -e "${red}uninstall${normal}:	\t\tremove the installed modules and overlays"
echo -e "${red}check${normal}:	\t\t\tcheck the build environment and build all without installing"

echo
