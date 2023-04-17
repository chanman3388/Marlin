"""
Module for ui elements for auto_build
"""
import logging
import sys
try:
    # python 2
    import Queue as queue
    import Tkinter as tk
    from Tkinter import ttk
    from Tkinter import tkFileDialog as filedialog
except (ImportError, ModuleNotFoundError):
    # python 3
    import tkinter as tk
    from tkinter import ttk
    from tkinter import filedialog
    import queue
from threading import Event, Lock, Thread

from auto_build.pio import run_PIO
import auto_build.constants
import auto_build.utils
#########
#  Python 2 error messages:
#    Can't find a usable init.tcl in the following directories ...
#    error "invalid command name "tcl_findLibrary""
#
#  Fix for the above errors on my Win10 system:
#    search all init.tcl files for the line "package require -exact Tcl" that has the highest 8.5.x number
#    copy it into the first directory listed in the error messages
#    set the environmental variables TCLLIBPATH and TCL_LIBRARY to the directory where you found the init.tcl file
#    reboot
#########


class UserPopup:
    """The class for the user popup interface"""
    current_answer = 2  # Initialize the default answer to the bottom

    def __init__(self, board_name, title, choices):
        self.board_name = board_name
        self.title = title
        self.choices = choices

        self.popup = tk.Tk()
        self.popup.title(board_name)
        self.popup.attributes("-topmost", True)
        # self.popup.protocol("WM_DELETE_WINDOW", self.disable_event)
        self.popup.resizable(False, False)
        self.mainframe = ttk.Frame(self.popup, padding="3 3 12 12")
        self.popup.radio_state = 0
        self.radio_state = tk.IntVar()
        self.radio_state.set(len(self.choices)-1)
        self._answer = self.radio_state.get()
        # labels
        label_style = ttk.Style()
        label_style.configure("top.TLabel", foreground="light green", background="dark green",
                              font="default 14 bold")
        ttk.Label(self.popup, text=self.board_name, style="top.TLabel",
                  ).grid(row=0, columnspan=2, sticky='EW', ipadx=2, ipady=2)
        ttk.Label(self.popup, text=self.title).grid(row=1, pady=4, columnspan=2, sticky='EW')
        # radiobuttons
        radio_button_style = ttk.Style()
        radio_button_style.configure("top.TRadiobutton",
                                     relief=tk.RAISED, indicatorrelief=tk.FLAT,
                                     indicatormargin=-1, indicatordiameter=-1,
                                     focusthickness=0, highlightthickness=0,
                                     indicatoron=False, padding=5)
        radio_button_style.map("top.TRadiobutton",
                               background=[("selected", "white"), ("active", "green")])
        row = 1
        for value, choice in enumerate(self.choices):
            ttk.Radiobutton(
                self.popup, style="top.TRadiobutton",
                text=choice, width=35,
                variable=self.radio_state, value=value,
                command=self.set_answer
            ).grid(row=row, pady=1, ipady=2, ipadx=10, columnspan=2)
            row += 1

        tk.Button(self.popup, text="Cancel", fg="red", command=sys.exit
                  ).grid(row=row, column=0, padx=4, pady=4, ipadx=2, ipady=2)
        tk.Button(self.popup, text="Continue", fg="green", command=self.popup.destroy
                  ).grid(row=row, column=1, padx=4, pady=4, ipadx=2, ipady=2)

        self.popup.bind("Return", self.popup.destroy)
        self.popup.mainloop()

    @property
    def answer(self):
        """Return the answer"""
        return self._answer


    def set_answer(self):
        """Set the answer"""
        self._answer = self.radio_state.get()


def get_answer(board_name, title, choices):
    """
    :param board_name str:
    :param title str:
    :param choices List[str]:
    """
    user_popup = UserPopup(board_name, title, choices)
    return user_popup.answer


class OutputWindow(tk.Text):
    """based on Super Text"""
    search_position = ''  # start with invalid search position
    error_found = False  # are there any errors?

    def __init__(self, pio_args):
        self.root = tk.Tk()
        self.root.attributes("-topmost", True)
        self.frame = tk.Frame(self.root)
        self.frame.pack(fill='both', expand=True)
        self.pio_args = pio_args
        self.filename = ""
        self.secondary_thread = None
        self.line_queue = queue.Queue()
        self.lock = Lock()
        self.should_exit = Event()
        self.logger = logging.getLogger(self.__class__.__name__)


        # text widget
        #self.text = tk.Text(self.frame, borderwidth=3, relief="sunken")
        tk.Text.__init__(self, self.frame, borderwidth=3, relief="sunken")
        self.config(tabs=(400, ))  # configure Text widget tab stops
        self.config(background='black', foreground='white', font=("consolas", 12), wrap='word', undo='True')
        #self.config(background = 'black', foreground = 'white', font= ("consolas", 12), wrap = 'none', undo = 'True')
        self.config(height=24, width=100)
        self.config(insertbackground='pale green')  # keyboard insertion point
        self.pack(side='left', fill='both', expand=True)

        self.tag_config('normal', foreground='white')
        self.tag_config('warning', foreground='yellow')
        self.tag_config('error', foreground='red')
        self.tag_config('highlight_green', foreground='green')
        self.tag_config('highlight_blue', foreground='cyan')
        self.tag_config('error_highlight_inactive', background='dim gray')
        self.tag_config('error_highlight_active', background='light grey')

        self.bind_class("Text", "<Control-a>", self.select_all)  # required in windows, works in others
        self.bind_all("<Control-Shift-E>", self.scroll_errors)
        self.bind_class("<Control-Shift-R>", self.rebuild)

        # scrollbar
        scrb = tk.Scrollbar(self.frame, orient='vertical', command=self.yview)
        self.config(yscrollcommand=scrb.set)
        scrb.pack(side='right', fill='y')

        # pop-up menu
        self.popup = tk.Menu(self, tearoff=0)

        self.popup.add_command(label='Copy', command=self.copy)
        self.popup.add_command(label='Paste', command=self._paste)
        self.popup.add_separator()
        self.popup.add_command(label='Cut', command=self.cut)
        self.popup.add_separator()
        self.popup.add_command(label='Select All', command=self.select_all)
        self.popup.add_command(label='Clear All', command=self._clear_all)
        self.popup.add_separator()
        self.popup.add_command(label='Save As', command=self._file_save_as)
        self.popup.add_separator()
        #self.popup.add_command(label='Repeat Build(CTL-shift-r)', command=self._rebuild)
        self.popup.add_command(label='Repeat Build', command=self._rebuild)
        self.popup.add_separator()
        self.popup.add_command(label='Scroll Errors (CTL-shift-e)', command=self._scroll_errors)
        self.popup.add_separator()
        self.popup.add_command(label='Open File at Cursor', command=self._open_selected_file)

        if auto_build.constants.CURRENT_OS == 'Darwin':  # MAC
            self.bind('<Button-2>', self._show_popup)  # macOS only
        else:
            self.bind('<Button-3>', self._show_popup)  # Windows & Linux

    # threading & subprocess section

    def start_thread(self):
        """
        create then start a secondary thread to run an arbitrary function
        must have at least one argument
        """
        # self.secondary_thread = Thread(target=lambda q, arg1: q.put(run_PIO(*self.pio_args, self.line_queue)),
        #                                args=(queue.Queue(), ''))
        self.logger.debug("Starting PIO thread")
        self.secondary_thread = Thread(target=run_PIO, args=list(self.pio_args) + [self.line_queue])
        self.secondary_thread.start()
        # check the Queue in 50ms
        self.root.after(50, self.check_thread)
        self.root.after(50, self.update)

    def check_thread(self):
        """wait for user to kill the window"""
        with self.lock:
            if not self.should_exit.is_set():
                self.root.after(10, self.check_thread)

    def update(self):
        with self.lock:
            if not self.should_exit.is_set():
                self.root.after(10, self.update)  #method is called every 50ms
            temp_text = ['0', '0']
        if self.line_queue.empty():
            if not self.secondary_thread.is_alive():
                with self.lock:
                    self.should_exit.set()  # queue is exhausted and thread is dead so no need for further updates
        else:
            try:
                temp_text = self.line_queue.get(block=False)
            except queue.Empty:
                self.should_exit.set()  # queue is exhausted so no need for further updates
            else:
                self.insert('end', temp_text[0], temp_text[1])
                self.see("end")  # make the last line visible (scroll text off the top)
                self.line_queue.task_done()

    # text editing section

    def _scroll_errors(self):
        if self.search_position == '':  # first time so highlight all errors
            count_var = tk.IntVar()
            self.search_position = '1.0'
            search_count = 0
            while self.search_position != '' and search_count < 100:
                self.search_position = self.search(
                    "error", self.search_position,
                    stopindex="end", count=count_var, nocase=1)
                search_count += 1
                if self.search_position != '':
                    self.error_found = True
                    end_pos = '{}+{}c'.format(self.search_position, 5)
                    self.tag_add("error_highlight_inactive", self.search_position, end_pos)
                    # point to the next character for new search
                    self.search_position = '{}+{}c'.format(self.search_position, 1)
                else:
                    break

        if self.error_found:
            if not self.search_position:
                self.search_position = self.search(
                    "error", '1.0', stopindex="end", nocase=1)  # new search
            else:  # remove active highlight
                end_pos = '{}+{}c'.format(self.search_position, 5)
                start_pos = '{}+{}c'.format(self.search_position, -1)
                self.tag_remove("error_highlight_active", start_pos, end_pos)
            self.search_position = self.search(
                "error", self.search_position, stopindex="end", nocase=1
            )  # finds first occurrence AGAIN on the first time through
            if not self.search_position:  # wrap around
                self.search_position = self.search(
                    "error", '1.0', stopindex="end", nocase=1)
            end_pos = '{}+{}c'.format(self.search_position, 5)
            # add active highlight
            self.tag_add("error_highlight_active", self.search_position, end_pos)
            self.see(self.search_position)
            # point to the next character for new search
            self.search_position = '{}+{}c'.format(self.search_position, 1)

    def scroll_errors(self, _):
        self._scroll_errors()

    def _rebuild(self):
        self.start_thread()

    def rebuild(self, _):
        self._rebuild()

    def _open_selected_file(self):
        current_line = self.index('insert')
        line_start = current_line[:current_line.find('.')] + '.0'
        line_end = current_line[:current_line.find('.')] + '.200'
        self.mark_set("path_start", line_start)
        self.mark_set("path_end", line_end)
        path = self.get("path_start", "path_end")
        from_loc = path.find('from ')
        colon_loc = path.find(': ')
        if 0 <= from_loc and ((colon_loc == -1) or (from_loc < colon_loc)):
            path = path[from_loc + 5:]
        if 0 <= colon_loc:
            path = path[:colon_loc]
        if 0 <= path.find('\\') or 0 <= path.find('/'):  # make sure it really contains a path
            auto_build.utils.open_file(path)

    def _file_save_as(self):
        self.filename = filedialog.asksaveasfilename(defaultextension='.txt')
        with open(self.filename, "w") as f:
            f.write(self.get('1.0', 'end'))

    def copy(self, _):
        try:
            selection = self.get(*self.tag_ranges('sel'))
            self.clipboard_clear()
            self.clipboard_append(selection)
        except TypeError:
            pass

    def cut(self, _):
        try:
            selection = self.get(*self.tag_ranges('sel'))
            self.clipboard_clear()
            self.clipboard_append(selection)
            self.delete(*self.tag_ranges('sel'))
        except TypeError:
            pass

    def _show_popup(self, event):
        '''right-click popup menu'''
        if self.root.focus_get() != self:
            self.root.focus_set()

        try:
            self.popup.tk_popup(event.x_root, event.y_root, 0)
        finally:
            self.popup.grab_release()


    def _paste(self):
        self.insert('insert', self.selection_get(selection='CLIPBOARD'))

    # def _select_all(self):
    #     self.tag_add('sel', '1.0', 'end')

    def select_all(self, _):
        self.tag_add('sel', '1.0', 'end')

    def _clear_all(self):
        #'''erases all text'''
        #
        #isok = askokcancel('Clear All', 'Erase all text?', frame=self,
        #                   default='ok')
        #if isok:
        #    self.delete('1.0', 'end')
        self.delete('1.0', 'end')


class ScreenWriter(Thread):
    """Class to handle screen writing"""
    PLATFORMIO_HIGHLIGHTS = (
        ['Environment', 0, 'highlight_blue'], ['[SKIP]', 1, 'warning'], ['[IGNORED]', 1, 'warning'], ['[ERROR]', 1, 'error'],
        ['[FAILED]', 1, 'error'], ['[SUCCESS]', 1, 'highlight_green']
    )

    def __init__(self, pio_subprocess, line_queue):
        Thread.__init__(self)
        self.pio_subprocess = pio_subprocess
        self.line_queue = line_queue
        self.warning = False
        self.warning_FROM = False
        self.error = False
        self.standard = True
        self.prev_line_COM = False
        self.next_line_warning = False
        self.warning_continue = False
        self.line_counter = 0
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("init")

    def run(self):
        self.logger.info("Running main thread")
        for line in iter(self.pio_subprocess.stdout.readline,
                         '' if auto_build.constants.PYTHON_VER == 2 else b''):
            if auto_build.constants.PYTHON_VER == 3:
                line = line.decode('utf-8')
            self.line_print(line.replace("\n", ""))

    def write_to_screen_queue(self, text, format_tag="normal"):
        """Add something to the screen queue"""
        self.line_queue.put([text, format_tag], block=False)

    def write_to_screen_with_replace(self, text):
        """search for highlights & split line accordingly"""
        # somehwere below, non-error lines are repeated 5 times
        did_something = False
        for highlight in ScreenWriter.PLATFORMIO_HIGHLIGHTS:
            found = text.find(highlight[0])
            if did_something is True:
                break
            if found >= 0:
                did_something = True
                if highlight[1] == 0:
                    found_1 = text.find(' ')
                    found_tab = text.find('\t')
                    if found_1 < 0 or found_1 > found_tab:
                        found_1 = found_tab
                self.write_to_screen_queue(text[:found_1 + 1])
                for highlight_2 in ScreenWriter.PLATFORMIO_HIGHLIGHTS:
                    if highlight[0] == highlight_2[0]:
                        continue
                    found = text.find(highlight_2[0])
                    if found >= 0:
                        found_space = text.find(' ', found_1 + 1)
                        found_tab = text.find('\t', found_1 + 1)
                        if found_space < 0 or found_space > found_tab:
                            found_space = found_tab
                        found_right = text.find(']', found + 1)
                        self.write_to_screen_queue(text[found_1 + 1:found_space + 1], highlight[2])
                        self.write_to_screen_queue(text[found_space + 1:found + 1])
                        self.write_to_screen_queue(text[found + 1:found_right], highlight_2[2])
                        self.write_to_screen_queue(text[found_right:] + '\n')
                        break
                    break
                if highlight[1] == 1:
                    found_right = text.find(']', found + 1)
                    self.write_to_screen_queue(text[:found + 1])
                    self.write_to_screen_queue(text[found + 1:found_right], highlight[2])
                    self.write_to_screen_queue(text[found_right:] + '\n' + '\n')
                    break
        if did_something is False:
            if not text.startswith("\r") and not text.endswith("\r"):  # need to split this line
                for line in text.split("\r"):
                    if line:
                        self.write_to_screen_queue(line + '\n')
            else:
                self.write_to_screen_queue(text + '\n')

    def line_print(self, line):
        """Process the line and add to screen queue"""
        self.line_counter += 1
        max_search = len(line)
        if max_search > 3:
            max_search = 3
        beginning = line[:max_search]

        # set flags
        if ": warning: " in line:  # start of warning block
            self.warning = True
            self.warning_FROM = False
            self.error = False
            self.standard = False
            self.prev_line_COM = False
            self.warning_continue = True
        if any(item in line for item in ("Thank you", "SUMMARY")):
            self.warning = False  #standard line found
            self.warning_FROM = False
            self.error = False
            self.standard = True
            self.prev_line_COM = False
            self.warning_continue = False
        elif any(item in beginning for item in ("War", "#er", "In")) or \
                (beginning != "Com" and self.prev_line_COM is True and \
                    all(item not in beginning for item in ("Arc", "Lin", "Ind")) \
                    or self.next_line_warning is True):
            self.warning = True  #warning found
            self.warning_FROM = False
            self.error = False
            self.standard = False
            self.prev_line_COM = False
        elif any(item in beginning for item in ("Com", "Ver", " [E", "Rem", "Bui", "Ind", "PLA")):
            self.warning = False  #standard line found
            self.warning_FROM = False
            self.error = False
            self.standard = True
            self.prev_line_COM = False
            self.warning_continue = False
        elif beginning == '***':
            self.warning = False  # error found
            self.warning_FROM = False
            self.error = True
            self.standard = False
            self.prev_line_COM = False
        elif any(error_msg in line for error_msg in (": error:", ": fatal error:")):  # start of warning /error block
            self.warning = False  # error found
            self.warning_FROM = False
            self.error = True
            self.standard = False
            self.prev_line_COM = False
            self.warning_continue = True
        elif beginning == 'fro' and self.warning is True or \
                beginning == '.pi':  # start of warning /error block
            self.warning_FROM = True
            self.prev_line_COM = False
            self.warning_continue = True
        elif self.warning_continue is True:
            self.warning = True
            self.warning_FROM = False  # keep the warning status going until find a standard line or an error
            self.error = False
            self.standard = False
            self.prev_line_COM = False
            self.warning_continue = True
        else:
            self.warning = False  # unknown so assume standard line
            self.warning_FROM = False
            self.error = False
            self.standard = True
            self.prev_line_COM = False
            self.warning_continue = False

        if beginning == 'Com':
            self.prev_line_COM = True

        # print based on flags
        if self.standard is True:
            self.write_to_screen_with_replace(line)  #print white on black with substitutions
        if self.warning is True:
            self.write_to_screen_queue(line + '\n', 'warning')
        if self.error is True:
            self.write_to_screen_queue(line + '\n', 'error')
