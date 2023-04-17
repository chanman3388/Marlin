"""
Module for finding the various environments
"""
import logging
import os
import re

import auto_build.constants
from auto_build.ui import get_answer
from auto_build.utils import _check_am_in_base_dir


LOGGER = logging.getLogger(__name__)



def get_board_name():
    """
    Get the board being built from the Configuration.h file
    :return: board name, major version of Marlin being used (1 or 2)
    """
    _check_am_in_base_dir()
    board_name = ''
    # get board name

    with open('Marlin/Configuration.h') as myfile:
        config_h = myfile.read()

    for line in config_h.split("\n"):
        if "#define CONFIGURATION_H_VERSION" in line:
            marlin_ver = int(re.search(r"\s(\d{2})", line).group(1))
            assert marlin_ver in auto_build.constants.EXPECTED_MARLIN_VERSIONS
        if "MOTHERBOARD" in line:
            board_match = re.match(r"\s+#define\sMOTHERBOARD\s(BOARD\w+)$", line)
            if board_match:
                board_name = board_match.group(1)
                return board_match.group(1), marlin_ver

    assert board_name != ""


def get_build_last():
    """Get the last build"""
    _check_am_in_base_dir()
    env_last = ''
    if '.pio' in os.listdir('.'):
        date_last = 0.0
        for name in os.listdir('.pio'):
            if any(skip_char in name for skip_char in ".-"):  # skip files in listing
                continue
            for names_temp in os.listdir("./pio/build/" + name):
                date_temp = sorted(
                    filter(
                        lambda folder: "firmware." in folder, os.listdir(
                            ".pio/build/" + name + "/" + names_temp)),
                    key=os.path.getmtime)[-1]
                if date_temp > date_last:
                    date_last = date_temp
                    env_last = name
    return env_last


def find_env_from_ini_file(base_marlin_dir):
    """find the env from the ini file
    :param base_marlin_dir str: the base marlin directory
    :returns str: the environment from default_envs
    """
    with open(os.path.join(base_marlin_dir, "platformio.ini")) as file:
        for line in file.readlines():
            if line.startswith("default_envs"):
                return line.strip().split(" ")[-1]

    return ""  # we should never hit this, this is just for pylint


def get_envs(full_board_name, marlin_version):
    """Retrieve the envs for the full_board_name
    based on which Marlin version one is using.
    :param full_board_name str: full board name in the form BOARD_<rest_of_name>
    :param marlin_version int: the marlin major version as an integer
    :returns List[str]: list of envs, each expected to be of the form "env:<rest_of_env>"
    """
    LOGGER.info("Retrieving environments for board %s Marlin version %d",
                full_board_name, marlin_version)
    try:
        path = {
            1: "Marlin/pins.h",
            2: "Marlin/src/pins/pins.h"
        }[marlin_version]
    except KeyError:
        raise EnvironmentError("Marlin version {} no yet supported".format(marlin_version))

    with open(path) as myfile:
        pins_h = myfile.read()
    # only use the part after "BOARD_" since we're searching the pins.h file
    board_name = full_board_name[6:]
    pins_h_lines = pins_h.split('\n')
    list_start_found = False
    for i, line in enumerate(pins_h_lines):
        if "Unknown MOTHERBOARD value set in Configuration.h" in line:
            break  #  no more
        if "1280" in line:
            list_start_found = True
        if list_start_found is False:  # skip line until find start of CPU list
            continue
        if board_name in line:  # need to look at the next line for environment info
            # we have detected the 'if' line, cpu info is on next line
            return [item[4:] for item in pins_h_lines[i+1].split(" ") if "env" in item]

    return []


def get_target_env(full_board_name, marlin_version, build_type):
    """Determine the target env based on the full_board_name
    :param full_board_name str: full board name in the form of BOARD_<rest_of_name>
    :parm marlin_version int: the marlin major version as an integer
    :param build_type str: the build arg supplied
    """
    # determine envs available
    # find the smallest subset, and offer the options thereafter unless only one
    envs_for_board = get_envs(full_board_name, marlin_version)
    if not envs_for_board:
        raise EnvironmentError("No environment for {}".format(full_board_name))
    if len(envs_for_board) == 1:
        env = envs_for_board[0]
        if env == "LPC1768":
            if (build_type == "traceback" or
                    (build_type == "clean" and get_build_last() == "LPC1768_debug_and_upload")):
                env += "_debug_and_upload"
        elif env == "DUE":
            if (build_type == "traceback" or
                    (build_type == "clean" and get_build_last() == "DUE_debug")):
                env += "_debug"
        return env

    # present all the options otherwise
    answer = get_answer(full_board_name, title="Pick", choices=envs_for_board)
    env = envs_for_board[answer]
    if (build_type == "traceback" and
            env not in ("LPC1768_debug_and_upload", "DUE_debug") and marlin_version == 2):
        EnvironmentError("ERROR - this board isn't setup for traceback")
    return envs_for_board[answer]
