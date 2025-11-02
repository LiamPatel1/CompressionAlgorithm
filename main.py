from glob import glob
import json
import os
from string import ascii_uppercase
import threading
import tkinter
from datetime import datetime
from time import time
from tkinter import colorchooser, ttk, messagebox
from PIL import ImageTk, Image
import tarfile

import huffman
import encrypt


class Icon:
    def __init__(self, path):     # class for each file icon that encapsulates image manipulation
        self.icon = Image.open(path)
        if 'arrow' not in path:
            self.icon = self.icon.resize((20, 28))
        self.tk = ImageTk.PhotoImage(self.icon)


class Item(tkinter.Button):
    def __init__(self, parent, path, index, frame):
        super().__init__(frame, compound='left', justify='left', anchor='w', relief='flat',
                         bg=parent.primary_colour, foreground=parent.text_colour)

        self.parent = parent   # keeps a pointer to the explorer frame
        self.path = path     # path that the Item represents
        self.selected = False
        self.rightclick_menu = tkinter.Menu(parent, tearoff=0)
        self.rightclick_menu.add_command(label='Open externally', command=lambda x=self.path: os.startfile(x))

        image_formats = ['.png', '.jpg', '.jpeg', '.gif']
        text_formats = ['.txt', '.doc', '.docx', '.pdf']
        self.icon = parent.file_icon.tk
        self.file_type = 'file'
        if os.path.isdir(self.path):               # sets what icon should be shown next to the file
            self.file_type = 'dir'
            self.icon = self.parent.folder_icon.tk
        elif os.path.splitext(self.path)[1] in image_formats:
            self.icon = self.parent.image_icon.tk
        elif os.path.splitext(self.path)[1] in text_formats:
            self.icon = self.parent.text_icon.tk

        self.configure(image=self.icon)

        self.bind('<Shift-Button-1>', lambda event, item=self, click_type='shift': self.parent.click(self, click_type))
        self.bind('<Button-1>', lambda event, item=self, click_type='single': self.parent.click(self, click_type))
        self.bind('<Button-3>', lambda event, item=self, click_type='right': self.parent.click(self, click_type))
        self.bind('<Double-Button-1>',
                  lambda event, item=self, click_type='double': self.parent.click(self, click_type))
        self.bind('<Shift-Button-3>',
                  lambda event, item=self, click_type='right_shift': self.parent.click(self, click_type))

    def toggle_select(self, result=None):
        if result == 0:
            self.selected = False
            self.configure(bg=self.parent.primary_colour)
        elif result == 1:
            self.selected = True
            self.configure(bg=self.parent.secondary_colour)
        else:
            if self.selected is False:
                self.selected = True
                self.configure(bg=self.parent.secondary_colour)
            else:
                self.selected = False
                self.configure(bg=self.parent.primary_colour)


class ShortcutButton(Item):             # class for Items that appear in the shortcut window on the left
    def __init__(self, parent, path, index):
        super().__init__(parent, path, index, parent.shortcuts_frame.interior_frame)
        self.rightclick_menu.add_command(label='Remove Shortcut', command=self.remove_shortcut)
        self.text = os.path.normpath(self.path)
        self.grid(sticky='ew', column=0, row=index)
        if len(self.text) > 30:               # if the path is too long, don't show all of it
            self.text = self.text[:27] + "..."
        self.configure(text=self.text)

    def remove_shortcut(self):
        self.parent.shortcuts.remove(self.path)
        self.parent.update_items()
        self.parent.update_configs()

    def delete(self):
        self.destroy()


class ExplorerButton(Item):
    def __init__(self, parent, path, index):
        super().__init__(parent, path, index, parent.explorer_frame.interior_frame)
        self.grid(sticky='ew', column=0, row=index, ipadx=60)

        self.rightclick_menu.add_command(label='Add to Archive', command=parent.create_archive_window)
        self.rightclick_menu.add_command(label='Decompress Archive', command=parent.decompress_archive_window)
        self.rightclick_menu.add_command(label='Add to Shortcuts', command=self.add_shortcut)
        self.selected = False
        self.file_size = os.stat(self.path).st_size

        try:
            self.last_modified = datetime.fromtimestamp(os.stat(self.path).st_mtime)
            self.last_modified = str(self.last_modified.replace(microsecond=0))
        except OSError:
            print(f'error finding metadata for {self.path}')
            self.last_modified = ''

        if self.file_size > 1e9:         # depending on the file size, change to display in KB or MB or GB or just B
            self.file_size = str(float('%.3g' % (self.file_size / 1e9))) + " GB"
        elif self.file_size > 1e6:
            self.file_size = str(float('%.3g' % (self.file_size / 1e6))) + " MB"
        elif self.file_size > 1e3:
            self.file_size = str(float('%.3g' % (self.file_size / 1e3))) + " KB"
        else:
            self.file_size = str(self.file_size) + " B"

        self.size_label = tkinter.Label(parent.explorer_frame.interior_frame, text=self.file_size,
                                        foreground=parent.text_colour, background=parent.primary_colour, pady=9,
                                        padx=20,
                                        justify='left')
        self.size_label.grid(row=index, column=1, sticky='we')

        self.last_modified_label = tkinter.Label(parent.explorer_frame.interior_frame, text=self.last_modified,
                                                 foreground=parent.text_colour, background=parent.primary_colour,
                                                 pady=9,
                                                 justify='left', padx=40)
        self.last_modified_label.grid(row=index, column=2, sticky='we')
        self.text = os.path.split(self.path)[-1]         # returns only the filename from the whole filepath
        if len(self.text) > 60:       # if path is too long, don't display all of it
            self.text = self.text[:57] + "..."
        self.configure(text=self.text, image=self.icon)

    def add_shortcut(self):
        self.parent.shortcuts.append(self.path)
        self.parent.update_items()
        self.parent.update_configs()

    def delete(self):
        self.size_label.destroy()
        self.last_modified_label.destroy()
        self.destroy()


class ScrollableFrame(tkinter.Frame):  # Custom tkinter widget, tkinter does not allow frames to scroll normally
    def __init__(self, padx, width, height, parent):
        super().__init__()
        self.parent = parent    # keeps pointer to parent frame
        self.width = width
        self.height = height
        self.grid(row=1, column=0, sticky='w', padx=padx)
        self.canvas = tkinter.Canvas(self)    # creates a canvas, which tkinter does allow to scroll
        self.interior_frame = tkinter.Frame(self.canvas)
        self.scrollbar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(anchor='w')
        self.canvas.create_window((0, 0), window=self.interior_frame)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.interior_frame.bind("<Configure>", self.update_exterior)

    def update_exterior(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"), width=self.width, height=self.height)

    def change_colour(self):
        self.canvas.configure(bg=self.parent.primary_colour)


class Main(tkinter.Tk):
    def __init__(self):
        super().__init__()
        with open('configs.json', 'r') as f:       # load settings from file
            configs = json.load(f)
            self.primary_colour = configs["PrimaryColour"]          # str (hex)
            self.secondary_colour = configs['SecondaryColour']      # str (hex)
            self.text_colour = configs['TextColour']                # str (hex)
            self.shortcuts = configs['Shortcuts']                   # [str]
            self.initial_directory = configs['InitialDirectory']    # str
            self.remember_directory = configs['RememberDirectory']  # bool
            self.last_directory = configs['LastDirectory']          # str

        self.style = tkinter.ttk.Style()
        self.style.theme_use('classic')

        self.style.configure("Vertical.TScrollbar", troughcolor=self.primary_colour, arrowcolour=self.secondary_colour,
                             bordercolor=self.secondary_colour, background=self.secondary_colour)
        self.mouse_x = 0
        self.mouse_y = 0
        self.bind('<Motion>', self.motion)       # binds mouse movement to method
        self.file_icon = Icon("images/file.png")
        self.image_icon = Icon("images/image.png")
        self.folder_icon = Icon("images/folder.png")
        self.text_icon = Icon("images/text.png")
        self.arrow_icon = Icon("images/arrow.png")

        self.geometry("1100x750")

        if self.remember_directory:
            self.current_dir = self.last_directory
        else:
            self.current_dir = self.initial_directory

        self.items = []
        self.shortcut_items = []

        self.explorer_frame = ScrollableFrame(padx=235, width=800, height=700, parent=self)
        self.shortcuts_frame = ScrollableFrame(padx=0, width=200, height=700, parent=self)

        self.textbar_frame = tkinter.Frame(self)
        self.textbar_frame.grid(column=0, row=0, columnspan=2)
        self.textbar_dir = tkinter.StringVar()
        self.textbar_entry = tkinter.Entry(self.textbar_frame, width=250, textvariable=self.textbar_dir)
        self.textbar_entry.bind('<Return>', lambda e: self.entry_update())
        self.textbar_back_button = tkinter.Button(self.textbar_frame, width=35, height=10, image=self.arrow_icon.tk,
                                                  command=self.back)
        self.textbar_back_button.grid(column=0, row=0)
        self.textbar_entry.grid(sticky='we', column=1, row=0)

        self.menu = tkinter.Menu(self)
        self.menu_file = tkinter.Menu(self.menu, tearoff=0)
        self.menu_file.add_command(label='Refresh', command=self.update_items)
        self.menu.add_cascade(label='File', menu=self.menu_file)
        self.menu_options = tkinter.Menu(self.menu, tearoff=0)
        self.menu_options.add_command(label='Settings', command=lambda: self.settings_window())

        self.menu.add_cascade(label='Options', menu=self.menu_options)
        self.config(menu=self.menu)
        self.update_items()

        self.name_column = tkinter.Label(self.explorer_frame.interior_frame, text='Name')
        self.name_column.grid(column=0, row=0, sticky='w')
        self.date_column = tkinter.Label(self.explorer_frame.interior_frame, text='File Size', padx=22)
        self.date_column.grid(column=1, row=0, sticky='w')
        self.time_column = tkinter.Label(self.explorer_frame.interior_frame, text='Date modified', padx=54)
        self.time_column.grid(column=2, row=0, sticky='w')

        self.change_colour('primary', self.primary_colour)
        self.change_colour('secondary', self.secondary_colour)
        self.change_colour('text', self.text_colour)

    def update_configs(self):
        configs = {'PrimaryColour': self.primary_colour,
                   'SecondaryColour': self.secondary_colour,
                   'TextColour': self.text_colour,
                   'Shortcuts': self.shortcuts,
                   'InitialDirectory': self.initial_directory,
                   'RememberDirectory': self.remember_directory,
                   "LastDirectory": self.last_directory
                   }

        with open('configs.json', 'w') as f:
            json.dump(configs, f, indent=4)

    def update_items(self):  # Refreshes UI

        for item in self.items + self.shortcut_items:  # Clears current items
            item.delete()

        self.items = []
        self.shortcut_items = []

        input_files = glob(self.current_dir + "/*")  # gets list of files from the selected directory

        for index, input_file in enumerate(input_files):  # Creates items in the explorer window
            self.items.append(ExplorerButton(path=input_file, parent=self, index=index + 1))

        drive_letters = []
        for i in ascii_uppercase:       # finds all drive letters in the computer
            if os.path.exists(i + ':'):
                drive_letters.append(i + ':')

        for index, shortcut in enumerate(self.shortcuts + drive_letters):  # Creates items in the shortcuts window
            self.shortcut_items.append(ShortcutButton(path=shortcut, parent=self, index=index))

        self.textbar_entry.delete(0, tkinter.END)
        self.textbar_entry.insert(0, os.path.normpath(self.current_dir))  # alter textbar to display current directory

        self.last_directory = self.current_dir
        self.update_configs()

    def motion(self, event):  # Keeps track of mouse position
        self.mouse_x = event.x_root
        self.mouse_y = event.y_root

    def entry_update(self):  # Updates the UI when a new directory is entered in the top entry
        self.current_dir = self.textbar_entry.get()
        self.update_items()

    def back(self):  # Updates the UI when the back button is pressed
        self.current_dir = ''.join(os.path.split(self.current_dir)[:-1])
        self.update_items()

    def create_archive_window(self):
        CreateArchive(self)

    def settings_window(self):
        Settings(self)

    def decompress_archive_window(self):
        for item in self.items:
            if item.selected:
                DecompressArchive(self, item)

    def click(self, clicked_item, click_type):    # called when a file is clicked on

        if click_type == 'single':
            if type(clicked_item).__name__ == 'ShortcutButton':
                self.current_dir = clicked_item.path
                self.update_items()
            else:
                for item in self.items:
                    item.toggle_select(0)

                clicked_item.toggle_select(1)

        elif click_type == 'double':
            if clicked_item.file_type == 'dir':
                self.current_dir = clicked_item.path
                self.update_items()

        elif click_type == 'shift':
            clicked_item.toggle_select()

        elif click_type == 'right':
            for item in self.items:
                item.toggle_select(0)
            clicked_item.toggle_select(1)
            clicked_item.rightclick_menu.tk_popup(self.mouse_x, self.mouse_y)

        elif click_type == 'right_shift':
            clicked_item.toggle_select(1)
            clicked_item.rightclick_menu.tk_popup(self.mouse_x, self.mouse_y)

    def change_colour(self, colour_type, colour=None):  # updates colour of the UI
        if colour is None:
            colour = tkinter.colorchooser.askcolor(title=f'Change {colour_type} colour')[1]
        if colour_type == 'primary':
            self.primary_colour = colour
        elif colour_type == 'secondary':
            self.secondary_colour = colour
        elif colour_type == 'text':
            self.text_colour = colour
            self.update_items()

        self.configure(bg=self.secondary_colour)
        self.shortcuts_frame.change_colour()
        self.explorer_frame.change_colour()
        self.style.configure("Vertical.TScrollbar", troughcolor=self.primary_colour, arrowcolour=self.secondary_colour,
                             bordercolor=self.secondary_colour, background=self.secondary_colour)
        self.update_configs()


class Settings(tkinter.Toplevel):
    def __init__(self, parent):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self.save)       # saves settings whenever window is closed

        self.parent = parent
        self.primary_colour_button = tkinter.Button(self, text='Primary Colour', foreground=parent.text_colour,
                                                    command=lambda: self.parent.change_colour('primary'))
        self.primary_colour_button.grid(column=0, row=0)
        self.primary_colour_label = tkinter.Label(self, padx=20, pady=10, background=parent.primary_colour)
        self.primary_colour_label.grid(column=1, row=0, padx=5)
        self.secondary_colour_button = tkinter.Button(self, text='Secondary Colour', foreground=parent.text_colour,
                                                      command=lambda: self.parent.change_colour('secondary'))
        self.secondary_colour_button.grid(column=0, row=1)
        self.secondary_colour_label = tkinter.Label(self, padx=20, pady=10, background=parent.secondary_colour)
        self.secondary_colour_label.grid(column=1, row=1, padx=5)
        self.text_colour_button = tkinter.Button(self, text='Text Colour', foreground=parent.text_colour,
                                                 command=lambda: self.parent.change_colour('text'))
        self.text_colour_button.grid(column=0, row=2)
        self.text_colour_label = tkinter.Label(self, padx=20, pady=10, background=parent.text_colour)
        self.text_colour_label.grid(column=1, row=2, padx=5)

        self.remember_var = tkinter.BooleanVar()
        self.remember_radiobutton = tkinter.Radiobutton(self, command=self.remember_dir_click,
                                                        text='Remember Last Directory', variable=self.remember_var,
                                                        value=True)

        self.default_radiobutton = tkinter.Radiobutton(self, command=self.default_dir_click,
                                                       text='Default to directory', variable=self.remember_var,
                                                       value=False)
        self.remember_radiobutton.grid(column=0, row=3)
        self.default_radiobutton.grid(column=0, row=4)

        self.default_entry = tkinter.Entry(self)
        self.default_entry.insert(0, self.parent.initial_directory)
        self.default_entry.grid(column=1, row=4)

        self.remember_var.set(self.parent.remember_directory)
        if self.remember_var.get():
            self.default_entry.configure(state='disabled')

    def remember_dir_click(self):
        self.default_entry.configure(state='disabled')
        self.parent.remember_directory = True

    def default_dir_click(self):
        self.default_entry.configure(state='normal')
        self.parent.remember_directory = False

    def save(self):
        self.parent.initial_directory = self.default_entry.get()
        self.parent.update()
        self.destroy()


class CreateArchive(tkinter.Toplevel):
    def __init__(self, parent):
        super().__init__()
        self.grab_set()
        self.parent = parent
        self.task_thread = threading.Thread(target=self.confirm_archive) # runs compression on another thread
        self.input_files = []
        for i in parent.items:
            if i.selected:
                self.input_files.append(i.path)
        if len(self.input_files) > 1:
            initial_dir = parent.current_dir + "/" + os.path.split(parent.current_dir)[-1] + ".z"
        else:
            initial_dir = parent.current_dir + "/" + os.path.split(self.input_files[0])[-1].split(".")[0] + ".z"

        self.geometry("500x500")
        archive_label = tkinter.Label(self, text="Archive:")
        archive_label.grid(row=0, column=0)
        self.archive_entry_text = tkinter.StringVar()
        self.archive_entry = tkinter.Entry(self, textvariable=self.archive_entry_text, width=70)
        self.archive_entry.insert(0, initial_dir)
        self.archive_entry.grid(row=0, column=1)
        self.password_label = tkinter.Label(self, text='Enter Password (leave blank for none)')
        self.password_label.grid(column=0, row=3)
        self.password_entry = tkinter.Entry(self, foreground=self.parent.text_colour)
        self.password_entry.grid(column=0, row=4)
        self.confirm_button = tkinter.Button(self, text="Confirm", command=self.task_thread.start)
        self.confirm_button.grid(row=1, column=0, columnspan=2)

        self.progress_bar = ttk.Progressbar(self, mode='indeterminate', length=250)
        self.progress_label = tkinter.Label(self, text='')
        self.progress_label.grid(column=0, row=4, columnspan=2)

    def confirm_archive(self):
        archive_path = self.archive_entry.get()
        if os.path.exists(archive_path) is True:
            overwrite_warning = tkinter.messagebox.askokcancel(title='Compression Warning', message='Path already exists. Overwrite file?', parent=self)
            if overwrite_warning is False:
                return 0

        password = self.password_entry.get()


        block_size = 1000
        self.confirm_button['state'] = 'disabled'
        start = time()
        self.progress_bar.grid(column=0, row=2, columnspan=2)
        self.progress_bar.start()

        archive_path = self.archive_entry.get()
        archive = tarfile.open('temp', 'w:')
        for i in self.input_files:
            archive.add(i)
        archive.close()

        with open('temp', 'rb') as f:
            data = huffman.compress(f.read(), block_size)
        with open(archive_path, 'wb') as f:
            if password != '':
                data = encrypt.encrypt(data, password)

            f.write(data)
        os.remove('temp')
        self.parent.update_items()
        tkinter.messagebox.showinfo(title='Compression successful', message=f'Completed in {"%.2f" % float(time() - start)} seconds')
        self.destroy()


class DecompressArchive(tkinter.Toplevel):
    def __init__(self, parent, item):
        super().__init__()
        self.parent = parent
        self.task_thread = threading.Thread(target=self.confirm_decompress) # runs decompression on another thread

        self.parent = parent
        self.progress_bar = ttk.Progressbar(self, mode='indeterminate', length=250)
        self.progress_bar.grid(column=0, row=2, columnspan=2)
        initial_dir = item.path.split(".")[0]
        self.geometry("500x500")
        archive_label = tkinter.Label(self, text="Output:")
        archive_label.grid(row=0, column=0)
        self.archive_entry_text = tkinter.StringVar()
        self.archive_entry = tkinter.Entry(self, textvariable=self.archive_entry_text, width=70)
        self.archive_entry.insert(0, initial_dir)
        self.archive_entry.grid(row=0, column=1)
        self.confirm_button = tkinter.Button(self, text="Decompress", command=self.task_thread.start)
        self.confirm_button.grid(row=1, column=0, columnspan=2)
        self.password_label = tkinter.Label(self, text='Enter Password (leave blank for none)')
        self.password_label.grid(column=0, row=3)
        self.password_entry = tkinter.Entry(self, foreground=self.parent.text_colour)
        self.password_entry.grid(column=0, row=4)

    def confirm_decompress(self):
        self.confirm_button['state'] = 'disabled'
        archive_path = self.archive_entry.get()
        self.progress_bar.start()
        password = self.password_entry.get()
        selected_items = []
        for item in self.parent.items:
            if item.selected:
                selected_items.append(item)

        for item in selected_items:
            with open(item.path, 'rb') as f:
                data = f.read()
                if password != '':
                    data = encrypt.decrypt(data, password)
                decompressed_data = huffman.decompress(data)
                if decompressed_data == 0:
                    tkinter.messagebox.showerror(title='Decompression error', message='Incorrect password or corrupted file')
                    return 0
            with open('temp', 'wb') as f:
                f.write(decompressed_data)
        archive = tarfile.open('temp', 'r:')

        archive.extractall(path=archive_path)
        archive.close()
        os.remove('temp')
        self.destroy()


if __name__ == '__main__':
    window = Main()
    window.mainloop()

