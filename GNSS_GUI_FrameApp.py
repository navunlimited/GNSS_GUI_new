import kivy
kivy.require("1.10.0")
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.scrollview import ScrollView
from kivy.uix.dropdown import DropDown
# from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty, ListProperty, StringProperty
from kivy.clock import Clock
import os, serial, io
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo
from kivy.lang import Builder
#from TerminalWindow import CommandTerminal, DataScroll
from TerminalWindow import *
import threading, time, queue

Clock.max_iteration = 30
Builder.load_file('GNSS_GUI_Frame.kv')
Builder.load_file('TerminalWindow.kv')

class BackgroundColor(Widget):
    pass


class MenuDropdown(BoxLayout):
    # add dropdown items#
    pass


class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class StatusTab(TabbedPanel):
    # add tabs for display system information: system info tab, RTK tab, IMU tab
    path_info = ObjectProperty()
    filename_input = ObjectProperty()
    btn_logging = ObjectProperty()

    dataQueue = queue.Queue(maxsize=500)
    logging_status = False
    file_path = ''
    file_abs = ''
    fdLog = io.IOBase()

    def __init__(self, **kwargs):
        super(StatusTab, self).__init__(**kwargs)
        self.writeTrd = threading.Thread(target=self.do_writting, args=())
        '''----other data storage ----'''
        self.UTCtime = ['00', '00', '00.000']  #RMC, GLL, GGA, ZDA,
        self.secCount = 0
        self.pre_UTCtime = ['00', '00', '00.000']
        self.GPStime = ['0000', '000000.000']
        self.posLLA = ['00', '00.000000', 'N', '000', '00.000000', 'W'] #RMC, GLL, GGA
        self.velocity = '000.0'  #RMC, VTG,
        self.heading = '000.0'   #RMC, VTG,
        self.solution_status = ['0', '0', ' ', '','','','','','','']  # number of SV in solution, solution type, FAA mode, [3:9], GSA field:8-14
        # 0:number of SV in solution- GSA, 1: solution_type - GSA, 2: FAA mode - RMC, GLL, VTG
        self.DOP = ['0.0', '0.0', '0.0']  #GSA
        self.date =['00', '00', '0000']   #date from RMC ddmmyy, ZDA
        self.local_zone=['', '']  #ZDA
        self.GGA = False
        self.RMC = False
        self.GLL = False
        self.GSA = False
        self.GSV = False
        self.VTG = False
        self.ZDA = False
        self.bind(size = self.update_fontsize)

    def UTCtoSecond(self, utc):
        second = utc[0]*3600 + utc[1]*60 + utc[2]
        return second

    def SecondtoUTC(self, second):
        if -86400 <= second < 0:
            second = 86400 + second
        else:
            return -1

        min_sec = second % 3600
        hr = (second - min_sec)/3600
        sec = min_sec % 60
        min = (min_sec - sec) / 60
        return [hr, min, sec]


    def update_info_label(self):
        self.info_label.text = ("""   [b]UTC time:[/b] {0}hr {1}min {2}sec  [b]Position:[/b] {3}deg {4}min {5}, {6}deg {7}min {8}  """
                                """[b]No. sv in sol:[/b] {9}  [b]FAA mode:[/b] {18}\n"""
                                """   [b]GPS time:[/b] {13}wk {14}sec  [b]Ground vel:[/b] {15}[b]m/s[/b]  [b]Heading:[/b] {16}deg  """
                                """[b]Sol. type:[/b] {17}  [b]DOP- P:[/b] {10}, [b]H:[/b] {11}, [b]V:[/b] {12}""".format(
                                self.UTCtime[0], self.UTCtime[1], self.UTCtime[2], self.posLLA[0], self.posLLA[1], self.posLLA[2],
                                self.posLLA[3], self.posLLA[4], self.posLLA[5], self.solution_status[0], self.DOP[0], self.DOP[1],
                                self.DOP[2], self.GPStime[0], self.GPStime[1], self.velocity, self.heading,
                                self.solution_status[1], self.solution_status[2]))

        if self.secCount == 0:
            #utc = [int(self.UTCtime[0]), int(self.UTCtime[1]), float(self.UTCtime[2])]
            #temp_sec = self.UTCtoSecond(utc)
            #temp_utc = self.SecondtoUTC(temp_sec -1)
            self.pre_UTCtime[0] = self.UTCtime[0]
            self.pre_UTCtime[1] = self.UTCtime[1]
            self.pre_UTCtime[2] = self.UTCtime[2]
            self.secCount += 1
        else:
            utc = [int(self.UTCtime[0]), int(self.UTCtime[1]), float(self.UTCtime[2])]
            sec = self.UTCtoSecond(utc)
            utc0 = [int(self.pre_UTCtime[0]), int(self.pre_UTCtime[1]), float(self.pre_UTCtime[2])]
            sec0 = self.UTCtoSecond(utc0)
            if sec - sec0 > 1:
                print('Larg time gap found: ' + str(sec-sec0))
                print('current UTC: {0} {1} {2}; preveous UTC: {3} {4} {5}'.format(self.UTCtime[0],
                self.UTCtime[1], self.UTCtime[2], self.pre_UTCtime[0], self.pre_UTCtime[1], self.pre_UTCtime[2]))

            self.pre_UTCtime[0] = self.UTCtime[0]
            self.pre_UTCtime[1] = self.UTCtime[1]
            self.pre_UTCtime[2] = self.UTCtime[2]
            self.secCount += 1


    def update_fontsize(self, instance, value):
        Clock.schedule_once(self.updateNow, 0)  #call at next frame, so width is updated already
        #print('value: ' + str(value))
        #print('instance info_label width: ' + str(instance.info_label.width))
        #print('self info_label width: ' + str(self.info_label.width))

    def updateNow(self, dt):
        #print('updateNow: self info_label width: ' + str(self.info_label.width))
        if 14 <= self.info_label.width/55  < 18:
            self.info_label.font_size = self.info_label.width/55
        elif self.info_label.width/55 >= 18:
            self.info_label.font_size = 18
        else:
            self.info_label.font_size = 14
        #print('label font size: ' + str(self.info_label.font_size))

    def dismiss_popup(self):
        self._popup.dismiss()

    def show_popup(self):
        if not self.logging_status:
            content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
            self._popup = Popup(title="Select directiory/file", content=content,
                                size_hint=(0.9, 0.9))
            self._popup.open()

    def load(self, path, filename):
        print('path: ' + path)
        print('select file: ' + filename)
        self.file_path = path + '\\'
        if filename == '':
            self.file_abs = path + '\\'
        else:
            rind = filename.rfind('\\')
            if rind > 0:
                fileonly = filename[rind+1:len(filename)]
            else:
                fileonly =''
            self.filename_input.text = fileonly
            self.file_abs = filename + '.log'
        self.path_info.text = ' Save data log at: ' + self.file_abs
        self.dismiss_popup()

    def do_filenameUpdate(self):
        if not self.logging_status:
            self.file_abs = self.file_path + self.filename_input.text + '.log'
            self.path_info.text = ' Save data log at: ' + self.file_abs

    def do_logging(self):
        if not self.logging_status:
            self.btn_logging.text = 'click to stop logging'
            print('open file : ' + self.file_abs)
            try:
                self.fdLog = open(self.file_abs, 'w')
                self.logging_status = True
                self.path_info.text = ' Save data  at: ' + self.file_abs + ' ; logging now....'
            except:
                print('open file fail: ' + self.file_abs)

            if self.logging_status:
                if not self.writeTrd.is_alive():
                    try:
                        self.writeTrd.start()
                    except RuntimeError:  # occurs if thread is dead
                        self.writeTrd = threading.Thread(target=self.do_writting, args=())
                        self.writeTrd.start()

        else:
            self.stop_logging()

    def stop_logging(self):
        self.logging_status = False
        self.writeTrd.join()
        print('exit writting thread')
        self.fdLog.close()
        self.btn_logging.text = 'click to start logging'
        self.do_filenameUpdate()

    def do_writting(self):
        while self.logging_status:
            numberQ = self.dataQueue.qsize()
            print('current dataQueue sizeto write: ' + str(numberQ))
            if numberQ > 0:
                for i in range(numberQ):
                    newText = self.dataQueue.get()
                    self.fdLog.write(newText)

            time.sleep(0.5)

    pass


class MainscreenTab(TabbedPanel):
    # add tabs at bottom right for mainscreen switching
    pass


class MainscreenLayout(BoxLayout):
    # add mainGNSS tab (SV_widge + Sky_Pos_Wdg), IMU configuration tab, wireless connection tab
    pass


class SvLayout(BoxLayout):
    # add constellation widget
    pass


class SkyPosWdg(BoxLayout):
    # add Sky_wdg and Pos_wdg
    pass


class Skywdg(Widget):
    pass


class Poswdg(Widget):
    pass


#class ConstellationWdg(ScrollView):
class ConstellationWdg(BoxLayout, StencilView, BackgroundColor):
    # add SVinfo class grouped by contellation
    def __init__(self, **kwargs):
        super(ConstellationWdg, self).__init__(**kwargs)
        self.adjustSVinfoTrd = threading.Thread(target=self.adjustSVinfo, args=())
        #self.pos_hint = {'top:': 1}
        self.orientation = 'vertical'
        #self.minimum_height = 12000
        self.padding = 2
        self.spacing = 1
        self.prnNum = 0
        self.numInWdg = 0
        self.nationID = ''
        self.prnlist = []  # store PRN number in svList, easy to fine corresponding SVinfo
        self.svlist = []
        self.prnInWdg = [] #PRN for showing in GUI due to size of GUI window size
        self.svInWdg = []
        self.decoded_SVinfo = []  # PRN list for the latest decoded SV list from GSV message
        self.updateDone = True
        self.textEnd = Label()  # used to fill out the bottom of BoxLayout
        self.add_widget(self.textEnd)

        #bind function for window size change
        self.bind(size=self.adjustSVinfoWrap)


    def update_svinfo(self):
        remove_list = []
        for i in range(self.prnNum):
            remove_list.append(i)

        for svin in self.decoded_SVinfo:
            newSV = False
            index_now = self.prnNum
            prn = svin[0]
            el = svin[1]
            az = svin[2]
            cn0 = svin[3]
            if index_now > 0:
                try:
                    idsv = self.prnlist.index(prn)
                except ValueError:
                    newSV = True
            else:
                newSV = True

            if newSV:
                sv = SVinfo()
                sv.index = index_now
                sv.nationID = self.nationID
                sv.sv_state.text = ('[b]PRN: ' + str(prn)  +
                                    ' EL: ' + str(el) + ' AZ: ' + str(az) + '[/b]')
                sv.cn0_wgt.bar1.value = cn0
                sv.l1cn0 = str(cn0)
                self.prnlist.append(prn)
                self.svlist.append(sv)
                self.prnNum += 1

                if self.height > (self.numInWdg+1)*(60+self.spacing):
                    self.numInWdg += 1
                    self.remove_widget(self.textEnd)
                    self.add_widget(sv)
                    self.add_widget(self.textEnd)
                    self.prnInWdg.append(prn)
                    self.svInWdg.append(sv)

            else:
                #print('existing SV found: ' + str(prn))
                remove_list[idsv] = -1
                self.svlist[idsv].sv_state.text = ('[b]PRN: ' + str(prn) +
                                                   ' EL: ' + str(el) + ' AZ: ' + str(az) + '[/b]')
                self.svlist[idsv].cn0_wgt.bar1.value = cn0
                self.svlist[idsv].l1cn0 = str(cn0)

        remove_list.reverse()
        for ind_svout in remove_list:
            if ind_svout != -1:
                prnout = self.prnlist[ind_svout]
                self.remove_svinfo(prnout)

        self.updateDone = True


    def remove_svinfo(self, prn):
        try:
            idrem = self.prnlist.index(prn)
            self.prnlist.pop(idrem)
            self.svlist.pop(idrem)
            self.prnNum -= 1
            idrem = self.prnInWdg.index(prn)
            self.prnInWdg.pop(idrem)
            self.remove_widget(self.svInWdg[idrem])
            self.svInWdg.pop(idrem)
            self.numInWdg -= 1
        except:
            pass

    def adjustSVinfo(self):     #adjust SVinfo displayed in GUI
        if self.height > self.numInWdg*(60+self.spacing) and self.numInWdg < self.prnNum:
            while self.height > (self.numInWdg+1)*(60+self.spacing) and self.numInWdg < self.prnNum:
                prn = self.prnlist[self.numInWdg]
                sv = self.svlist[self.numInWdg]
                self.remove_widget(self.textEnd)
                self.add_widget(sv)
                self.add_widget(self.textEnd)
                self.prnInWdg.append(int(prn))
                self.svInWdg.append(sv)
                self.numInWdg += 1
        elif self.height <= self.numInWdg*(60+self.spacing):
            while self.height <= self.numInWdg*(60+self.spacing) and self.numInWdg > 0:
                sv = self.svInWdg[self.numInWdg-1]
                self.remove_widget(self.textEnd)
                self.remove_widget(sv)
                self.add_widget(self.textEnd)
                self.prnInWdg.pop()
                self.svInWdg.pop()
                self.numInWdg -= 1

    def adjustSVinfoWrap(self, instance, value):
        if not self.adjustSVinfoTrd.is_alive():
            try:
                self.adjustSVinfoTrd.start()
            except RuntimeError:  # occurs if thread is dead
                self.adjustSVinfoTrd = threading.Thread(target=self.adjustSVinfo, args=())
                self.adjustSVinfoTrd.start()


class CN0(BoxLayout):
    def __init__(self, **kwargs):
        super(CN0, self).__init__(**kwargs)
        self.bar1 = L1cn0_ProgressBar(value=0, max=70)
        self.bar2 = L2cn0_ProgressBar(value=0, max=70)
        self.bar3 = L5cn0_ProgressBar(value=0, max=70)
        self.add_widget(self.bar1)
        self.add_widget(self.bar2)
        self.add_widget(self.bar3)
    pass


class ConnectionMenu(BoxLayout):
    # add serial/bluetooth/TcpIP connection dropdown menu
    readNum = 128           #read in byte number
    default_time_out = 5    # default time out
    clock_dt = 0.1
    ports = ListPortInfo
    deviceDetection = False
    list_speed = [50, 75, 110, 134, 150, 200, 300, 600, 1200,
                  1800, 2400, 4800, 9600, 19200, 38400, 57600, 115200,
                  230400, 460800, 500000, 576000, 921600, 1000000, 1152000,
                  1500000, 2000000, 2500000, 3000000, 3500000, 4000000]
    timeout = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50, 60, 120, 180, 300]

    # ===serial port info===#
    serlport = serial.Serial()  # serial object from python serial module
    serlio = io.TextIOWrapper(io.BufferedRWPair(serlport, serlport),
                              errors='ignore')  # TextIO wrapper, it decode binary to asceii and remove "/r"

    dropdownPort = DropDown()
    dropdownSpeed = DropDown()
    dropdownTimeout = DropDown()

    def __init__(self, **kwargs):
        super(ConnectionMenu, self).__init__(**kwargs)
        self.connectTrd1 = threading.Thread(target=self.do_connection, args=())
        self.connectTrd2 = threading.Thread(target=self.do_srlopen, args=())
        #self.connectTrd3 = threading.Thread(target=self.srlreadin, args=(), daemon=True)
        self.Trd1_startFlag = False


    def do_mainbtn_1_update(self, instance, x):
        self.mainbtn_1.select = True
        if (not self.mainbtn_2.select):
            self.btn_0.text = 'Please select Speed, then click'
        else:
            self.btn_0.text = 'Please click to connect !'
        print('The slected port is: {}'.format(x))

    def do_mainbtn_2_update(self, instance, x):
        self.mainbtn_2.select = True
        if (not self.mainbtn_1.select):
            self.btn_0.text = 'Please select Port, then click'
        else:
            self.btn_0.text = 'Please click to connect !'
        print('The slection speed is: {}'.format(x))

    def do_mainbtn_3_update(self, instance, x):
        self.mainbtn_3.select = True
        self.mainbtn_3.text = x
        if (not self.mainbtn_2.select) and self.mainbtn_1.select:
            self.btn_0.text = 'Please select Speed, then click'
        elif (not self.mainbtn_1.select) and self.mainbtn_2.select:
            self.btn_0.text = 'Please select Port, then click'
        elif self.mainbtn_1.select and self.mainbtn_2.select:
            self.btn_0.text = 'Please click to connect !'
        print('The slected timeout is: {}'.format(x))

    def update_btn0(self):
        print(self.deviceDetection)
        if not self.deviceDetection:
            self.btn_0.text = 'Port detecting....'
            print(self.btn_0.text)

    def do_connection(self):
        if (not self.deviceDetection):
            self.btn_0.text = 'Port detecting....'
            self.ports = list_ports.comports()
            for a in self.ports:
                btn = Button(text=a.device, size_hint_y=None, height=20)
                btn.bind(on_release=lambda btn: self.dropdownPort.select(btn.text))
                self.dropdownPort.add_widget(btn)

            for a in self.list_speed:
                btn = Button(text=str(a), size_hint_y=None, height=20)
                btn.bind(on_release=lambda btn: self.dropdownSpeed.select(btn.text))
                self.dropdownSpeed.add_widget(btn)

            self.mainbtn_1.bind(on_release=self.dropdownPort.open)
            self.dropdownPort.bind(on_select=lambda instance, x: setattr(self.mainbtn_1, 'text', x))
            self.dropdownPort.bind(on_select=self.do_mainbtn_1_update)

            self.mainbtn_2.bind(on_release=self.dropdownSpeed.open)
            self.dropdownSpeed.bind(on_select=lambda instance, x: setattr(self.mainbtn_2, 'text', x))
            self.dropdownSpeed.bind(on_select=self.do_mainbtn_2_update)

            for a in self.timeout:
                btn = Button(text=str(a) + ' s', size_hint_y=None, height=20)
                btn.bind(on_release=lambda btn: self.dropdownTimeout.select(btn.text))
                self.dropdownTimeout.add_widget(btn)

            self.mainbtn_3.bind(on_release=self.dropdownTimeout.open)
            # self.dropdownTimeout.bind(on_select = lambda instance, x: setattr(self.mainbtn_3, 'text', x) )
            self.dropdownTimeout.bind(on_select=self.do_mainbtn_3_update)
            self.deviceDetection = True
            self.btn_0.text = 'Please select Port/Speed'
            #print('about to exit T1 thread (do_connection) ....')

    def do_srlopen(self):
        if self.serlport.is_open:
            self.parent.terminal.dataview.stop_set = 1
            self.btn_0.text = 'Port disconnected'
        elif not self.mainbtn_1.select and self.mainbtn_2.select:
            self.btn_0.text = 'Please select Port, then click'
        elif self.mainbtn_1.select and not self.mainbtn_2.select:
            self.btn_0.text = 'Please select Speed, then click'
        elif self.mainbtn_1.select and self.mainbtn_2.select:
            self.serlport.port = self.mainbtn_1.text
            self.serlport.baudrate = int(self.mainbtn_2.text)
            if self.mainbtn_3.select:
                self.serlport.timeout = int(self.mainbtn_3.text.strip('s'))
            else:
                self.serlport.timeout = self.default_time_out

            print('trye to open port:' + self.serlport.port +
                  ' at speed :' + str(self.serlport.baudrate))
            try:
                self.serlport.open()
                print('serial open:' + self.serlport.port)
            except:
                print('open port failed ...')
                self.serlport.port = None
                self.serlport.baudrate = 9600
                self.serlport.timeout = None
                self.btn_0.text = 'Port connection fail'

            if self.serlport.is_open:
                if self.parent.terminal.dataview.loop_count > 0:
                    #print('re attach io.TextIOWrapper')
                    self.serlio = io.TextIOWrapper(io.BufferedRWPair(self.serlport, self.serlport),
                                                   errors = 'ignore')  # re-pairing
                newText = self.serlio.read(self.readNum)
                self.parent.terminal.dataview.text += newText
                self.btn_0.text = 'Port connected'
                self.srlreadin()


    def srlreadin(self):
        #print('Threading 2 is avlive? ' + str(self.connectTrd2.is_alive()))
        while self.parent.terminal.dataview.stop_set == 0:
            #if self.serlport.inWaiting() > 0:
            self.parent.terminal.dataview.loop_count += 1
            newText = self.serlio.read(self.readNum)

            #send newText to data log queue
            if self.parent.status.logging_status:
                self.parent.status.dataQueue.put(newText)

            #send newText to GUI decoding queue
            if not self.parent.msgQueue.full():
                self.parent.msgQueue.put(newText)
            else:
                pass
                #print('encoding megQueue is full !')

            if self.parent.terminal.dataview.pause_set == 0:
                self.parent.terminal.dataview.add_TextLine(newText)
            else:
                self.parent.terminal.dataview.pause_count += 1
                if self.parent.terminal.dataview.pause_count == 1:
                    newText = '\n .... Pause now .... \n'
                    self.parent.terminal.dataview.add_TextLine(newText)

            time.sleep(0.05)

        self.parent.terminal.dataview.stop_set = 0
        self.serlio.detach()
        self.serlport.close()
        self.parent.const_1.updateDone = True
        self.parent.const_2.updateDone = True

    def do_connectionWrap(self):
        if not self.deviceDetection:
            self.btn_0.text = 'Port detecting....'
            #print(self.btn_0.text)
            self.connectTrd1.start()
            self.Trd1_startFlag = True
            #self.connectTrd1.join()
        else:
            if self.connectTrd2.is_alive():
                self.parent.terminal.dataview.stop_set = 1
                self.btn_0.text = 'Port disconnected'
            else:
                try:
                    self.connectTrd2.start()
                    self.parent.decodeTrd.start()
                except RuntimeError:  # occurs if thread is dead
                    self.connectTrd2 = threading.Thread(target=self.do_srlopen, args=())
                    self.connectTrd2.start()
                    self.parent.decodeTrd = threading.Thread(target=self.parent.msg_decode, args=())
                    self.parent.decodeTrd.start()



class SVinfo(BoxLayout):
    # unit layout filled in with one SV information
    sv_state = ObjectProperty()
    cn0_wgt = ObjectProperty()

    def __init__(self, **kwargs):
        super(SVinfo, self).__init__(**kwargs)
        self.bind(size=self.update_fontsize)

    def update_fontsize(self, instance, value):
        Clock.schedule_once(self.updateNow, 0)  # call at next frame, so width is updated already

    def updateNow(self, dt):
        #print('updateNow: sv_state_label width: ' + str(self.sv_state.width))
        if 14 <= self.sv_state.width / 12 < 16:
            self.sv_state.font_size = self.sv_state.width / 12
        elif self.sv_state.width / 12 >= 16:
            self.sv_state.font_size = 16
        else:
            self.sv_state.font_size = 14
        #print('label font size: ' + str(self.sv_state.font_size))


class GNSSguiFrame(RelativeLayout):
    menuBtn1 = ObjectProperty()
    menuBtn2 = ObjectProperty()
    menuBtn3 = ObjectProperty()
    menuBtn4 = ObjectProperty()
    mainscreen = ObjectProperty()
    terminal = ObjectProperty()
    connection_menu = ObjectProperty()
    status = ObjectProperty()
    const_1 = ObjectProperty()
    const_2 = ObjectProperty()
    #info_label = ObjectProperty()

    '''dataview = ObjectProperty()
    btn_1 = ObjectProperty()
    textInput = ObjectProperty()
    command_rec = ObjectProperty()'''

    msgQueue = queue.Queue(maxsize=500)
    buff_text = ''

    def __init__(self, **kwargs):
        super(GNSSguiFrame, self).__init__(**kwargs)
        self.decodeTrd = threading.Thread(target=self.msg_decode, args=())
        self.const_1.nationID = 'GPS'
        self.const_2.nationID = 'GLO'

        #self.bind(size =self.update_fontsize)
        #self.decodeTrd.start()
        #print('start decodeTrd ?' + str(self.decodeTrd.is_alive()))


    def msg_decode(self): #pars and decoding NMEA message
        while self.connection_menu.connectTrd2.is_alive():
            numberQ = self.msgQueue.qsize()
            print('number of queue in msgQueue: {}'.format(numberQ))
            if numberQ > 0:
                for i in range(numberQ):
                    newText = self.msgQueue.get()
                    self.buff_text += newText

                numLine = self.buff_text.count('\n')
                if numLine > 0:
                    nmeaLine = self.buff_text.split('\n') #parse into lines
                    self.buff_text = nmeaLine.pop()       # pop out the last string for next time
                    for nmea in nmeaLine: #GGA, RMC, GLL, GSA, GSV, VTG, ZDA,
                        headcount = nmea.count('$')
                        checkcount = nmea.count('*')
                        if headcount == 1 and checkcount == 1:
                            if nmea[0] == '$' and nmea[3:6] == 'GGA': #position, velocity, UTC
                                self.decode_GGA(nmea)
                            elif nmea[0] == '$' and nmea[3:6] == 'RMC': #position, UTC
                                self.decode_RMC(nmea)
                            elif nmea[0] == '$' and nmea[3:6] == 'GLL' and not self.status.RMC: #position, UTC
                                self.decode_GLL(nmea)
                            elif nmea[0] == '$' and nmea[3:6] == 'GSA': #sv in solution, DOP
                                self.decode_GSA(nmea)
                            elif nmea[0] == '$' and nmea[3:6] == 'GSV': #SV in-view (svID, EL, AZ, SNR) a quadruple for each SV
                                self.decode_GSV(nmea)
                            elif nmea[0] == '$' and nmea[3:6] == 'VTG': #heading, speed and FAA mode indicattor
                                self.decode_VTG(nmea)
                            elif nmea[0] == '$' and nmea[3:6] == 'ZDA': #time information, UTC, year, moth day, localtime zone
                                self.decode_ZDA(nmea)
                            else:  #recode new message header.
                                if nmea[0] == '$' and nmea[3:6] != 'GLL':
                                    print('New NMEA message: ' + nmea)

            time.sleep(1)


    def decode_GGA(self, nmea):  #fixed 15 fields
        if nmea[3:6] != 'GGA':
            print('incorrect GGA message parsing!')
            return
        else:
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if len(textnow)!=15:
                print('GGA message field length is not 15 (exlude checksum)!; length is:' + str(len(textnow)))
                return

            if textnow[6] == '0':
                return          #no solution, no need to decode
            if not self.status.GGA:
                self.status.GGA = True

            if not self.status.RMC and not self.status.GLL:
                self.status.UTCtime[0] = textnow[1][0:2]
                self.status.UTCtime[1] = textnow[1][2:4]
                self.status.UTCtime[2] = textnow[1][4:len(textnow[1])]
                self.status.posLLA[0] = textnow[2][0:2]
                self.status.posLLA[1] = textnow[2][2:len(textnow[2])]
                self.status.posLLA[2] = textnow[3]
                self.status.posLLA[3] = textnow[4][0:3]
                self.status.posLLA[4] = textnow[4][3:len(textnow[4])]
                self.status.posLLA[5] = textnow[5]

                if float(self.status.UTCtime[2]).is_integer():
                    self.status.update_info_label()

            self.status.solution_status[0] = textnow[7]
            self.status.solution_status[1] = textnow[6]

            self.status.solution_status[3] = textnow[8]
            self.status.solution_status[4] = textnow[9]
            self.status.solution_status[5] = textnow[10]
            self.status.solution_status[6] = textnow[11]
            self.status.solution_status[7] = textnow[12]
            self.status.solution_status[8] = textnow[13]
            self.status.solution_status[9] = textnow[14]



    def decode_RMC(self, nmea):
        if nmea[3:6] != 'RMC':
            print('incorrect RMC message parsing!')
            return
        else:
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if len(textnow)!=13:
                print('RMC message field length is not 13 (exlude checksum)!; length is:' + str(len(textnow)))
                return

            if not self.status.RMC:
                if textnow[2] == 'A' or textnow[2] == 'a' :
                    self.status.RMC = True

            if self.status.RMC and (textnow[2] == 'A' or textnow[2] == 'a'):
                self.status.UTCtime[0] = textnow[1][0:2]
                self.status.UTCtime[1] = textnow[1][2:4]
                self.status.UTCtime[2] = textnow[1][4:len(textnow[1])]
                self.status.posLLA[0] = textnow[3][0:2]
                self.status.posLLA[1] = textnow[3][2:len(textnow[3])]
                self.status.posLLA[2] = textnow[4]
                self.status.posLLA[3] = textnow[5][0:3]
                self.status.posLLA[4] = textnow[5][3:len(textnow[5])]
                self.status.posLLA[5] = textnow[6]
                self.status.velocity = str(round(float(textnow[7]) * 0.51, 1))
                self.status.heading = textnow[8]
                self.status.date[0] = textnow[9][0:2]
                self.status.date[1] = textnow[9][2:4]
                self.status.date[2] = '20' + textnow[9][4:6]
                self.status.solution_status[2] = textnow[12]

            if float(self.status.UTCtime[2]).is_integer():
                #print('call update info at {} sec'.format(self.status.UTCtime[2]))
                self.status.update_info_label()

    def decode_GLL(self, nmea):
        if nmea[3:6] != 'GLL':
            print('incorrect GLL message parsing!')
            return
        else:
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if len(textnow) != 8:
                print('GLL message field length is not 8 (exlude checksum)!; length is:' + str(len(textnow)))
                return
            if not self.status.GLL:
                if textnow[6] == 'A' or textnow[6] == 'a':
                    self.status.GLL = True

            if self.status.GLL and (textnow[6] == 'A' or textnow[6] == 'a'):
                self.status.UTCtime[0] = textnow[5][0:2]
                self.status.UTCtime[1] = textnow[5][2:4]
                self.status.UTCtime[2] = textnow[5][4:len(textnow[5])]
                self.status.posLLA[0] = textnow[1][0:2]
                self.status.posLLA[1] = textnow[1][2:len(textnow[1])]
                self.status.posLLA[2] = textnow[2]
                self.status.posLLA[3] = textnow[3][0:3]
                self.status.posLLA[4] = textnow[3][3:len(textnow[3])]
                self.status.posLLA[5] = textnow[4]
                self.status.solution_status[2] = textnow[7]

                if float(self.status.UTCtime[2]).is_integer():
                    self.status.update_info_label()


    def decode_GSA(self, nmea):
        if nmea[3:6] != 'GSA':
            print('incorrect GSA message parsing!')
            return
        else:
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if len(textnow) != 18:
                print('GSA message field length is not 18 (exlude checksum)!; length is:' + str(len(textnow)))
                return

            if not self.status.GSA:
                if textnow[2] != '1':
                    self.status.GSA = True

            if self.status.GSA and textnow[2] != '1':
                self.status.DOP[0] = textnow[15]
                self.status.DOP[1] = textnow[16]
                self.status.DOP[2] = textnow[17]

    def decode_GSV(self, nmea):
        if nmea[3:6] != 'GSV':
            print('incorrect GSV message parsing!')
            return
        else:
            gsvnow =[]
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if (len(textnow) - 4) % 4 == 0:
                if not self.status.GSV:
                    self.status.GSV = True

                grNum = int((len(textnow) - 4) / 4)
                #print(nmea)
                #print('number of SVs: ' + str(grNum))
                #print(textnow)
                for i in range(grNum):
                    svinfo = []
                    #replace empty space for 0
                    for j in range(4):
                        if textnow[i*4+4+j] == '':
                            svinfo.append(0)
                        else:
                            svinfo.append(int(textnow[i*4+4+j]))

                    gsvnow.append(svinfo)

                if nmea[1:3] == 'GP':  # GPS constellation
                    if self.const_1.updateDone and textnow[2] == '1':
                        self.const_1.decoded_SVinfo =[]
                        self.const_1.updateDone = False

                    if not self.const_1.updateDone:
                        for svin in gsvnow:
                            self.const_1.decoded_SVinfo.append(svin)

                        if textnow[1] == textnow[2]:
                            self.const_1.update_svinfo()

                elif nmea[1:3] == 'GL':  # GLONASS constellation
                    if self.const_2.updateDone and textnow[2] == '1':
                        self.const_2.decoded_SVinfo =[]
                        self.const_2.updateDone = False

                    if not self.const_2.updateDone:
                        for svin in gsvnow:
                            self.const_2.decoded_SVinfo.append(svin)

                        if textnow[1] == textnow[2]:
                            self.const_2.update_svinfo()
            else:
                print('incorrect SV quadruple number!')
                return

    def decode_VTG(self, nmea):
        if nmea[3:6] != 'VTG':
            print('incorrect VTG message parsing!')
            return
        else:
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if len(textnow) != 10 and len(textnow) != 5:
                print('VTG message field length is not 5 or 10 (exlude checksum)!; length is:' + str(len(textnow)))
                return

            if len(textnow) == 10:
                if not self.status.VTG:
                    if textnow[9] != 'N':
                        self.status.VTG = True

                if self.status.VTG and textnow[9] != 'N':
                    if not self.status.RMC:
                        self.status.velocity = str(round(float(textnow[7]) * (1000/3600),1))
                        self.status.heading = textnow[1]
                        if not self.status.GLL:
                            self.status.solution_status[2] = textnow[9]

            else:
                if not self.status.VTG:
                    self.status.VTG = True
                    self.status.velocity = str(round(float(textnow[4]) * (1000/3600),1))
                    self.status.heading = textnow[1]

    def decode_ZDA(self, nmea):
        if nmea[3:6] != 'ZDA':
            print('incorrect ZDA message parsing!')
            return
        else:
            textnow = nmea.split(',')
            tt = textnow.pop()
            t1 = tt.split('*')
            if t1[0] == '':
                textnow.append('0')
            else:
                textnow.append(t1[0])

            if len(textnow) != 7:
                print('ZDA message field length is not 7 (exlude checksum)!; length is:' + str(len(textnow)))
                return

            if not self.status.ZDA:
                self.status.ZDA = True

            if self.status.ZDA:
                self.status.local_zone[0] = textnow[5]
                self.status.local_zone[1] = textnow[6]
                if not self.status.RMC and not self.status.GLL and not self.status.GGA:
                    self.status.UTCtime[0] = textnow[1][0:2]
                    self.status.UTCtime[1] = textnow[1][2:4]
                    self.status.UTCtime[2] = textnow[1][4:len(textnow[1])]

                    if float(self.status.UTCtime[2]).is_integer():
                        self.status.update_info_label()

                if not self.status.RMC:
                    self.status.date[0] = textnow[2]
                    self.status.date[1] = textnow[3]
                    self.status.date[2] = textnow[4]





class NavUnlimitedApp(App):
    myapp = GNSSguiFrame()
    def build(self):
        return self.myapp

    def on_stop(self):
        #stop logging thread and close file
        if self.myapp.status.logging_status:
            self.myapp.status.stop_logging()

        #stop reading thread, close serial port and stop decoding thread
        if self.myapp.connection_menu.connectTrd2.is_alive():
            self.myapp.terminal.dataview.stop_set = 1
            self.myapp.connection_menu.connectTrd2.join()
            self.myapp.decodeTrd.join()



if __name__ == '__main__':
    NavUnlimitedApp().run()
