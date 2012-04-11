import sublime
import sublime_plugin
from os import path
import tempfile
import desktop
import sys
import datetime

PACKAGE_SETTINGS = "PrintHtml.sublime-settings"

if sublime.platform() == "linux":
    # Try and load Linux Python2.6 lib.  Default path is for Ubuntu.
    linux_lib = sublime.load_settings(PACKAGE_SETTINGS).get("linux_python2.6_lib", "/usr/lib/python2.6/lib-dynload")
    if not linux_lib in sys.path and path.exists(linux_lib):
        sys.path.append(linux_lib)
from plistlib import readPlist


class PrintHtmlCommand(sublime_plugin.TextCommand):
    def setup(self, numbers, highlight_selections):
        path_packages = sublime.packages_path()

        # Get get general document preferences from sublime preferences
        settings = sublime.load_settings('Preferences.sublime-settings')
        self.font_size = settings.get('font_size') or 10
        self.font_face = settings.get('font_face') or 'Consolas'
        self.tab_size = settings.get('tab_size') or 4
        self.padd_top = settings.get('line_padding_top') or 0
        self.padd_bottom = settings.get('line_padding_bottom') or 0
        self.bground = ''
        self.fground = ''
        self.gbground = ''
        self.gfground = ''
        self.sbground = ''
        self.sfground = ''
        self.numbers = numbers
        self.highlight_selections = True
        self.hl_continue = None
        self.curr_hl = None

        # Get color scheme
        alt_scheme = sublime.load_settings(PACKAGE_SETTINGS).get("alternate_scheme", False)
        scheme_file = settings.get('color_scheme') if alt_scheme == False else alt_scheme
        colour_scheme = path.normpath(scheme_file)
        plist_file = readPlist(path_packages + colour_scheme.replace('Packages', ''))
        colour_settings = plist_file["settings"][0]["settings"]

        # Get general theme colors from color scheme file
        if "background" in colour_settings:
            self.bground = colour_settings["background"]
        if 'foreground' in colour_settings:
            self.fground = colour_settings["foreground"]
        if 'gutter' in colour_settings:
            self.gbground = colour_settings["gutter"]
        if 'gutterForeground' in colour_settings:
            self.gfground = colour_settings["gutterForeground"]
        if 'selectionForeground' in colour_settings:
            self.sfground = colour_settings["selectionForeground"]
        if 'selection' in colour_settings:
            self.sbground = colour_settings["selection"]

        if self.bground == '':
            self.bground == '#FFFFFF'

        if self.fground == '':
            self.fground == '#000000'

        if self.gfground == '':
            self.gfground = self.fground

        if self.gbground == '':
            self.gbground = self.bground

        if self.sfground == '':
            self.gfground = self.bground

        if self.sbground == '':
            self.sbground = self.fground

        # Determine start and end points and whether to parse whole file or selection
        curr_sel = self.view.sel()[0]
        if curr_sel.empty() or self.highlight_selections or abs(curr_sel.end() - curr_sel.begin()) < 4:
            self.size = self.view.size()
            self.pt = 0
            self.end = 1
            self.curr_row = 1
            self.partial = False
        else:
            self.size = curr_sel.end()
            self.pt = curr_sel.begin()
            self.end = self.pt + 1
            self.curr_row = self.view.rowcol(self.pt)[0] + 1
            self.partial = True

        self.gutter_pad = len(str(self.view.rowcol(self.size)[0])) + 1

        self.highlights = []
        if self.highlight_selections:
            for sel in self.view.sel():
                if not sel.empty():
                    self.highlights.append(sel)

        # Create scope colors mapping from color scheme file
        self.colours = {self.view.scope_name(self.end).split(' ')[0]: self.fground}
        for item in plist_file["settings"]:
            scope = None
            colour = None
            if 'scope' in item:
                scope = item['scope']
            if 'settings' in item and 'foreground' in item['settings']:
                colour = item['settings']['foreground']

            if scope != None and colour != None:
                self.colours[scope] = colour

    def print_line(self, line, num=None):
        if num == None:
            html_line = '<tr><td>%s</td></tr>' % line
        else:
            gutter = (
                '<span style=\"color: ' +
                self.gfground + ';\">' + str(num).rjust(self.gutter_pad).replace(" ", '&nbsp;') +
                '&nbsp;</span></td><td>'
            )
            html_line = '<tr><td style=\"background-color: ' + self.gbground + ';\">%s&nbsp;%s</td></tr>' % (gutter, line)
        return html_line

    def guess_colour(self, the_key):
        the_colour = None
        if the_key in self.colours:
            the_colour = self.colours[the_key]
        else:
            best_match = 0
            for key in self.colours:
                if self.view.score_selector(self.pt, key) > best_match:
                    best_match = self.view.score_selector(self.pt, key)
                    the_colour = self.colours[key]
            self.colours[the_key] = the_colour
        return the_colour

    def write_header(self, the_html):
        the_html.write('<!DOCTYPE html>\n')
        the_html.write('<html>\n<head>\n<title>' + path.basename(the_html.name) + '</title>\n')
        the_html.write('<style type=\"text/css\">\n')
        the_html.write('\tpre { border: 0; margin: 0; padding: 0;  }\n')
        the_html.write('\ttable { ')
        the_html.write('background-color: ' + self.bground + '; ')
        the_html.write('border: 0; margin: 0; padding: 0; }\n')
        the_html.write('\ttd { ')
        the_html.write(' font: ' + str(self.font_size) + 'pt \"' + self.font_face + '\", Consolas, Monospace; ')
        the_html.write('}\n')
        the_html.write('\tspan { border: 0; margin: 0; padding: 0; }\n')
        the_html.write('\tbody { ')
        the_html.write('color: ' + self.fground + '; ')
        the_html.write('background-color: ' + self.bground + '; ')
        the_html.write(' font: ' + str(self.font_size) + 'pt \"' + self.font_face + '\", Consolas, Monospace;')
        the_html.write('}\n')
        the_html.write('</style>\n</head>\n')

    def convert_view_to_html(self, the_html):
        for line in self.view.split_by_newlines(sublime.Region(self.end, self.size)):
            self.size = line.end()
            line = self.convert_line_to_html(the_html)
            if self.numbers:
                the_html.write(self.print_line(line, self.curr_row))
            else:
                the_html.write(self.print_line(line))
            self.curr_row += 1

    def convert_line_to_html(self, the_html):
        line = []
        hl_found = False

        # Continue highlight form last line
        if self.hl_continue != None:
            self.curr_hl = self.hl_continue
            self.hl_continue = None

        while self.end <= self.size:
            # Get next highlight region
            if self.highlight_selections and self.curr_hl == None and len(self.highlights) > 0:
                self.curr_hl = self.highlights.pop(0)

            # See if we are starting a highlight region
            if self.curr_hl != None and self.pt == self.curr_hl.begin():
                hl_found = True
                if self.curr_hl.end() <= self.size:
                    self.end = self.curr_hl.end()
                else:
                    # Highlight is bigger than line, mark for continuation
                    self.end = self.size
                    self.hl_continue = sublime.Region(self.size + 1, self.curr_hl.end())
            else:
                # Get text of like scope up to a highlight
                scope_name = self.view.scope_name(self.pt)
                while self.view.scope_name(self.end) == scope_name and self.end <= self.size:
                    # Kick out if we hit a highlight region
                    if self.curr_hl != None and self.end == self.curr_hl.begin():
                        break
                    self.end += 1
                the_colour = self.guess_colour(scope_name)

            # Format text to HTML
            tidied_text = self.view.substr(sublime.Region(self.pt, self.end))
            tidied_text = tidied_text.replace('&', '&amp;')
            tidied_text = tidied_text.replace('<', '&lt;')
            tidied_text = tidied_text.replace('>', '&gt;')
            tidied_text = tidied_text.replace('\t', ' ' * self.tab_size)
            tidied_text = tidied_text.replace("\n", '')
            tidied_text = tidied_text.replace(" ", '&nbsp;')

            # Highlight span if needed
            if hl_found:
                line.append('<span style=\"background-color:' + self.sbground + '; color:' + self.sfground + '\">')
                hl_found = False
                self.curr_hl = None
            else:
                line.append('<span style=\"color:' + the_colour + '\">')

            line.append(tidied_text + '</span>')
            self.pt = self.end
            self.end = self.pt + 1
        line.append('\n</span>')
        return ''.join(line)

    def write_body(self, the_html):
        the_html.write('<body>\n<pre>')

        # Write file name
        fname = self.view.file_name()
        if fname == None or not path.exists(fname):
            fname = "Untitled"
        date_time = datetime.datetime.now().strftime("%m/%d/%y %I:%M:%S ")
        the_html.write('<span style=\"color:' + self.fground + '\">' + date_time + fname + '\n\n</span>')

        the_html.write('<table cellspacing="0" cellpadding="0">')

        # Convert view to HTML
        self.convert_view_to_html(the_html)

        the_html.write('</table>')

        # Write empty line to allow copying of last line and line number without issue
        the_html.write('<pre/>\n</body>\n</html>')

    def run(self, edit, numbers=False, highlight_selections=False, clipboard=False):
        self.setup(numbers, highlight_selections)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as the_html:
            self.write_header(the_html)
            self.write_body(the_html)
            if clipboard:
                the_html.seek(0)
                sublime.set_clipboard(the_html.read())

        # Open in web browser
        desktop.open(the_html.name)
