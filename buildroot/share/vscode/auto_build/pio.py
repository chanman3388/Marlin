"""
"""
from datetime import datetime
import logging
import os
import subprocess

import auto_build.constants
import auto_build.ui


LOGGER = logging.getLogger(__name__)



def sys_PIO(build_type, target_env):

    ##########################################################################
    #                                                                        #
    # run Platformio inside the same shell as this Python script             #
    #                                                                        #
    ##########################################################################
    LOGGER.info("build_type: %s", build_type)
    LOGGER.info("starting platformio")

    if build_type == 'build':
        # pio_result = os.system("echo -en '\033c'")
        os.system('platformio run -e ' + target_env)
    elif build_type == 'clean':
        os.system('platformio run --target clean -e ' + target_env)
    elif build_type == 'upload':
        os.system('platformio run --target upload -e ' + target_env)
    elif build_type == 'traceback':
        os.system('platformio run --target upload -e ' + target_env)
    elif build_type == 'program':
        os.system('platformio run --target program -e ' + target_env)
    elif build_type == 'test':
        os.system('platformio test upload -e ' + target_env)
    elif build_type == 'remote':
        os.system('platformio remote run --target program -e ' + target_env)
    elif build_type == 'debug':
        os.system('platformio debug -e ' + target_env)
    else:
        raise EnvironmentError("ERROR - unknown build type: {}".format(build_type))

    # end - sys_PIO


def run_PIO(build_type, board_name, target_env, line_queue):
    LOGGER.info("build_type: %s", build_type)
    LOGGER.info("starting platformio")

    subprocess_args = ["platformio"]
    if "build" in build_type:
        subprocess_args.append("run")
    if build_type in ("clean", "program", "traceback", "upload"):
        subprocess_args.extend(["run", "--target", build_type])

    if build_type == 'test':
        #platformio test upload -e  target_env
        # combine stdout & stderr so all compile messages are included
        subprocess_args.extend(["test", "upload"])
    elif build_type == 'remote':
        # platformio remote run --target upload -e  target_env
        # combine stdout & stderr so all compile messages are included
        subprocess_args.extend(["remote", "run", "--target", "program"])
    elif build_type == 'debug':
        # platformio debug -e  target_env
        # combine stdout & stderr so all compile messages are included
        subprocess_args.append("debug")

    subprocess_args.extend(["-e", target_env])
    LOGGER.debug("pio args: %s", subprocess_args)
    pio_subprocess = subprocess.Popen(
        subprocess_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    screen_writer = auto_build.ui.ScreenWriter(pio_subprocess, line_queue)
    screen_writer.start()
    screen_writer.join()
    # append info used to run PlatformIO
    screen_writer.write_to_screen_queue('\nBoard name: ' + board_name + '\n')  # put build info at the bottom of the screen
    screen_writer.write_to_screen_queue('Build type: ' + build_type + '\n')
    screen_writer.write_to_screen_queue('Environment used: ' + target_env + '\n')
    screen_writer.write_to_screen_queue(str(datetime.now()) + '\n')
    LOGGER.debug("finished")
