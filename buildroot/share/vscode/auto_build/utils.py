""""""
import logging
import os
import subprocess

import auto_build.constants
#
# move custom board definitions from project folder to PlatformIO
#
LOGGER = logging.getLogger(__name__)


def _check_am_in_base_dir():
    pwd = os.getcwd().replace("\\", "/")  # make sure we're executing from the correct directory level
    if pwd != auto_build.constants.MARLIN_HOME_DIR:
        os.chdir(auto_build.constants.MARLIN_HOME_DIR)
    else:
        LOGGER.debug("Already in the base dir!")


def resolve_path(path):
    # turn the selection into a partial path
    LOGGER.info("This is the path: {}".format(path))
    if '"' in path:
        path = path[path.find('"'):]
        if ", line " in path:
            path = path.replace(', line ', ':')
            path = path.replace('"', '')
    LOGGER.info("This is the path: {}".format(path))
    # get line and column numbers
    line_num = 1
    column_num = 1
    line_start = path.find(':', 2)  # use 2 here so don't eat Windows full path
    column_start = path.find(':', line_start + 1)
    if column_start == -1:
        column_start = len(path)
    column_end = path.find(':', column_start + 1)
    if column_end == -1:
        column_end = len(path)
    if 0 <= line_start:
        line_num = path[line_start + 1:column_start]
        if line_num == '':
            line_num = 1
    if column_start != column_end:
        column_num = path[column_start + 1:column_end]
        if column_num == '':
            column_num = 0

    path = path.split(",")[0]  # delete comma and anything after
    index_end = path.find(':', 2)
    if 0 <= index_end:
        path = path[:path.find(':', 2)]  # delete the line number and anything after

    path = path.replace('\\', '/')

    if path[1] == ":" and auto_build.constants.CURRENT_OS == 'Windows':
        return path, line_num, column_num  # found a full path - no need for further processing
    elif path.startswith("/") and (auto_build.constants.CURRENT_OS in ('Darwin', 'Linux')):
        return path, line_num, column_num  # found a full path - no need for further processing
    else:
    # resolve as many '../' as we can
        path = path.replace("../", "")
        # while "../" in path:
        #     end = path.find('../') - 1
        #     start = path.find('/')
        #     while 0 <= path.find('/', start) and end > path.find('/', start):
        #         start = path.find('/', start) + 1
        #     path = path[0:start] + path[end + 4:]

  # this is an alternative to the above - it just deletes the '../' section
  # start_temp = path.find('../')
  # while 0 <= path.find('../',start_temp):
  #   start = path.find('../',start_temp)
  #   start_temp = start  + 1
  # if 0 <= start:
  #   path = path[start + 2 : ]

    # eat the spaces at the beginning
    if not path.startswith("/"):  # make sure path starts with '/'
        path = '/' + path.lstrip()  # eat any spaces at the beginning

    if auto_build.constants.CURRENT_OS == 'Windows':
        path = path.replace('/', '\\')  # os.walk uses '\' in Windows

    start_path = os.path.abspath('')

    # search project directory for the selection
    full_path = ''
    for root, directories, filenames in os.walk(start_path):
        for filename in filenames:
            if ".git" in root:  # don't bother looking in this directory
                break
            full_path = os.path.join(root, filename)
            if path in full_path:  # the path will exist, so we can safely return
                return full_path, line_num, column_num


def open_file(path):
    """
    Open the file in the preferred editor at the line & column number
    If the preferred editor isn't already running then it tries the next.
    If none are open then the system default is used.
    Editor order:
      1. Notepad++  (Windows only)
      2. Sublime Text
      3. Atom
      4. System default (opens at line 1, column 1 only)
    """
    file_path, line_num, column_num = resolve_path(path)
    if not file_path:
        return

    LOGGER.debug("Current OS: %s", auto_build.constants.CURRENT_OS)
    if auto_build.constants.CURRENT_OS == "Windows":
        """
        Output here will look something like one of:
            No Instance(s) Available.


        Or

            ExecutablePath
            <path to executable>

        Note the presence of 2 empty lines in absence of editors found in WINDOWS_EDITORS
        """
        def get_editor():
            for editor in auto_build.constants.EDITORS[auto_build.constants.CURRENT_OS]:
                executable_path = subprocess.check_output(
                    "wmic process where \"name='{}'\" get ExecutablePath".format(editor))
                if auto_build.constants.PYTHON_VER == 3:
                    executable_path = executable_path.decode("utf-8")
                if editor in executable_path:
                    return executable_path.split("\n")[1].strip()

        editor_path = get_editor()
        if editor_path:
            command_format_string = "{} -n{} -c{}" if "notepad++" in editor_path else "{}:{}:{}"
            subprocess.Popen([editor_path, command_format_string.format(file_path, line_num, column_num)])
        else:
            os.startfile(resolve_path(path))  # open file with default app
    elif auto_build.constants.CURRENT_OS in ("Linux", "Darwin"):
        command = "{}:{}:{}".format(file_path, line_num, column_num)
        if "," in command:
            # sometimes a comma magically appears at the end, we don't want it
            command = command.split(",")[0]


        def get_editor():
            running_apps = subprocess.Popen(
                "ps ax {} cmd".format(
                    {"Linux": "ax", "Darwin": "axwww"}[
                        auto_build.constants.CURRENT_OS]),
                stdout=subprocess.PIPE, shell=True)
            output, _ = running_apps.communicate()
            for editor in auto_build.constants.EDITORS[auto_build.constants.CURRENT_OS]:
                for line in output.split("\n"):
                    if editor in line:
                        if auto_build.constants.CURRENT_OS == "Darwin":
                            if "-psn" in line:
                                line = line[:path.find("-psn") - 1]
                        return True, line

            return False, ''

        found, editor_path = get_editor()
        if found:
            subprocess.Popen([editor_path, command])
        else:
            os.system("{}open {}".format("xdg-" if auto_build.constants.CURRENT_OS == "Linux" else "", file_path))
    else:
        print("Unsupported OS")

# end - open_file
