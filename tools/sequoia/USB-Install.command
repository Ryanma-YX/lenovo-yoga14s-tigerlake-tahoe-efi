#!/bin/bash
# Lives at the root of the USB data volume beside Sequoia-Setup.
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd -P)
case ${1:-target} in
    target) exec /bin/bash "$HERE/Sequoia-Setup/Recovery-Install.command" --show-target ;;
    install) exec /bin/bash "$HERE/Sequoia-Setup/Recovery-Install.command" ;;
    finish) exec /bin/bash "$HERE/Sequoia-Setup/Finish-Sequoia-USB.command" ;;
    *) echo 'Usage: bash INSTALL.command [target|install|finish]'; exit 1 ;;
esac
