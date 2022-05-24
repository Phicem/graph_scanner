#!/usr/bin/python3
### Architecture notes ###
# The model is an autonomous piece of software, it has its own features and its own specifications. It should not be used via signals but called directly. However, the model may send signals to notify its changes.
# The view is autonomous too. It provides with an interface from which low level signals (like a click) are sent. The view shoud not be smart.
# The application (controller) defines what happens when the low level signals are received.
# The application is the only part of sofware that knows about the others (model and view).
#
#

# To create a breakpoint:
#Qt.pyqtRemoveInputHook()
#pdb.set_trace()

import pdb
import time
from PyQt5 import QtGui, QtCore, QtSvg, Qt, QtWidgets
import os
import sys
sys.path.append('appdirs')
import appdirs
import webbrowser # to display help page

import logging
share_folder = './share/'

#logging.basicConfig(level=logging.DEBUG)

# Shortcuts
RightButton = QtCore.Qt.RightButton
LeftButton = QtCore.Qt.LeftButton
MiddleButton = QtCore.Qt.MiddleButton

# MODEL

class CModel(QtCore.QObject):
    """ The model is composed of:
    - self.list_of_points: a list of CModelPoints storing the coordinates of each point (in scene coordinates)
    - self.scale: a dict giving the scale in real world coordinates
    - self.borders: a dict giving the scale in scene coordinates
    - filename : the name of the image used
    """
    def __init__(self, GM):
        QtCore.QObject.__init__(self)
        self.dict_of_points = {}
        self.scale = {'xmin':'', 'ymin':'', 'xmax':'', 'ymax':''} # debug default
        self.borders = {'xmin':0., 'ymin':0., 'xmax':10., 'ymax':10.} # debug default
        self.filename = ''
        self.GM = GM

    def addPoint(self, x, y):
        if self.dict_of_points == {}:
            new_ref = 1
        else:
            new_ref = max(list(self.dict_of_points)) + 1
        self.dict_of_points[new_ref] = (x,y)
        logging.debug("add point at (%d, %d) in scene coordinates" % (x, y) )
        self.GM.addPoint(new_ref, x, y)

    def movePoint(self, ref, x, y):
        self.dict_of_points[ref] = (x,y)
        self.GM.movePoint(ref, x, y)

    def removePoint(self, ref):
        self.dict_of_points.pop(ref)
        self.GM.removePoint(ref)

    def removeAllPoints(self):
        for ref in list(self.dict_of_points): # the list() trick is mandatory because you can't remove items from a list you are itering on...
            self.removePoint(ref)

    def changeBorders(self, border_name, value):
        self.borders[border_name] = value
        self.GM.redrawBorders(self.borders['xmin'], self.borders['xmax'], 
                self.borders['ymin'], self.borders['ymax'])

    def changeBackground(self, filename):
        self.filename = filename
        self.removeAllPoints()
        self.GM.changeBackground(filename)

    def changeCoords(self, coord_name, coord_value):
        try:
            self.scale[coord_name] = float(coord_value)
        except:
            self.scale[coord_name] = ''
        self.GM.updateCoords(coord_name, coord_value) # useless for standard GUI usage, but necessary for command line use or undo stack

    def dumpModel(self):
        string = "MODEL DUMP\n"
        string += "Scale: " + str(self.scale) + '\n'
        string += "Borders: " + str(self.borders) + '\n'
        string += "Filename: " + self.filename + '\n'
        string += "Points:\n"
        for point in self.dict_of_points:
            string += 'point[%s] = (%s)\n' % (str(point), str(self.dict_of_points[point]))

        print(string)

    def convertPoint(self, x_scn, y_scn):
        x_ratio = ( x_scn - self.borders['xmin'] ) / ( self.borders['xmax'] - self.borders['xmin'] )
        y_ratio = ( y_scn - self.borders['ymin'] ) / ( self.borders['ymax'] - self.borders['ymin'] )
        y_ratio = 1 - y_ratio # Assumes that point (0,0) in the scene coord system is in the top left corner
        # TODO: at least warn the user about this in the help page
        
        x_out = self.scale['xmin'] + x_ratio * ( self.scale['xmax'] - self.scale['xmin'] )
        y_out = self.scale['ymin'] + y_ratio * ( self.scale['ymax'] - self.scale['ymin'] )


        return (x_out, y_out)

    def checkScale(self):
        try:
            for name in ['xmin', 'xmax', 'ymin', 'ymax']:
                #print(name)
                #print(not isinstance(self.scale[name], float))
                if not isinstance(self.scale[name], float):
                    return False
            if self.scale['xmin'] != self.scale['xmax'] and  self.scale['ymin'] != self.scale['ymax']:
                return True
        except:
            return False
        return False

    def exportData(self):
        if self.checkScale():
            list_of_points = []
            output = ""
            for point in self.dict_of_points:
                (x,y) = self.dict_of_points[point]
                (new_x, new_y) = self.convertPoint(x, y)
                list_of_points.append((new_x,new_y))
            sorted_list_of_points = sorted(list_of_points, key = lambda point: point[0])
            for point in sorted_list_of_points:
                (new_x,new_y) = point
                output +=  '%s%s%s\n' % (new_x, self.GM.param_manager.param_dict["output_separator"],new_y)
            Qt.QApplication.clipboard().setText(output)
            info_message = QtWidgets.QMessageBox(text="Output saved in clipboard")
            info_message.addButton(QtWidgets.QMessageBox.Ok)
            info_message.exec_()
                
                

        else:
            error_message = QtWidgets.QMessageBox(text="Invalid scale. Use '.' as the decimal symbol.")
            error_message.addButton(QtWidgets.QMessageBox.Ok)
            error_message.exec_()



# GUI MANAGER

class CUserParam:
    def __init__(self):
        self.user_dir = appdirs.user_data_dir(appname = "graphscanner",appauthor="graph")
        self.config_file_name = os.path.join(self.user_dir, "graph.conf")

        # Default values
        self.param_dict = {}
        self.param_dict["point_color"] = "red"
        self.param_dict["thin_line_color"] = "orange"
        self.param_dict["thick_line_color"] = "green"
        self.param_dict["border_width"] = 4
        self.param_dict["output_separator"] = "\t"

        self.readConfigFile()

    def readConfigFile(self):

        # Loading user custom parameters
        try:
            config_file = open(self.config_file_name,'rU') # universal new line
            for line in config_file.readlines():
                line = line.replace('\n','').replace(' ','')
                (param,value) = line.split("=")
                #print("Param %s loaded: value = %s" %(param,value) )
                self.param_dict[param] = value.decode("string_escape") # to handle tabs
            config_file.close()
        except:
            print("No config file found - creating one")
            self.writeConfigFile()


    def writeConfigFile(self):
        if not os.path.exists(self.user_dir):
            os.makedirs(self.user_dir)

        config_file = open(self.config_file_name,'wt')

        for key,elem in self.param_dict.items():
            line = "%s = %s\n" % (key,elem)
            config_file.write(line)

        config_file.close()


def displayHelpMessage():
#    webbrowser.open_new(
    module_dir = os.path.dirname(__file__)
    help_file = os.path.join(module_dir,"help","help.html")
    webbrowser.open_new(help_file)

class CGUIManager:
    """ The GUI has two missions:
    1/ To display the model
    2/ To catch user orders
    Thus, there must be a two-way communication between the GUI and the model. This class is an interface between the GUI and the model, and only that: it doesn't do much on its own.
    Input methods are here to transmit the model's orders to the GUI.Their prototype depend on the model, but not on the toolkit. Their implementation depends on the toolkit, but not on the model.
    Output methods are here to notify the model of any user input. Their prototypes depends on the GUI, but not on the model. Their implementation depend on the model, and not on the toolkit.
    """


    def __init__(self): # used for output methods
        self.param_manager = CUserParam()
        # used for drawing
        self.dict_of_points = {} # Could be stored in the GUI, but the way points are stored are important for good communication between the model and the GUI
        self.model = CModel(GM = self)
        self.GUI = CGUI(GM = self)


    # Input methods
    def addPoint(self, ref, x, y):
        self.dict_of_points[ref] = CGUIPoint(GM=self, ref=ref, x=x, y=y)

    def removePoint(self, ref):
        self.dict_of_points.pop(ref).removeFromScene()
        
    def movePoint(self, ref, x, y):
        self.dict_of_points[ref].move(x, y)

    def changeBackground(self, filename):
        self.GUI.win.canvas.setBackground(filename)

    def redrawBorders(self, xmin, xmax, ymin, ymax):
        self.GUI.win.canvas.borders.resizeRect(xmin, xmax, ymin, ymax)

    def updateCoords(self, coord_name, coord_value):
        pass # TODO: not implemented

    # Output methods
    def pointMustMove(self, ref, x, y):
        self.model.movePoint(ref, x, y)

    def pointMustDie(self, ref):
        self.model.removePoint(ref)

    def backgroundFileMustChange(self, new_file):
        self.model.changeBackgroundFile(new_file)

    def coordsMustChange(self, coord_name, coord_value):
        self.model.changeCoords(coord_name, coord_value)
    
    def bordersMustChange(self, border_name, value):
        self.model.changeBorders(border_name, value)

    def dataMustBeExported(self):
        self.model.exportData()



# GUI

def QPen(QColor,width):
    pen = QtGui.QPen(QColor)
    pen.setWidth(int(width))
    return pen

class CGUIPoint(QtWidgets.QGraphicsItemGroup):
    def __init__(self, GM, ref, x, y):
        self.ref = ref
        self.GM = GM
        QtWidgets.QGraphicsItemGroup.__init__(self, parent = None)
        # Configuring the item
        user_color =  self.GM.param_manager.param_dict["point_color"]
        pen = QPen(getQtColor(user_color), self.GM.GUI.pen_point_width)
        line_1 = QtWidgets.QGraphicsLineItem(-10, -10, 10, 10)
        line_1.setPen(pen)
        line_2 = QtWidgets.QGraphicsLineItem(-10, 10, 10, -10)
        line_2.setPen(pen)
        self.addToGroup(line_1)
        self.addToGroup(line_2)
        #self.setFlag(self.ItemIgnoresTransformations, True)
        self.GM.GUI.win.canvas.scene.addItem(self)

        self.setPos(x, y)
        self.setScale(self.GM.GUI.size_of_points)

    def mousePressEvent(self,event):
        if translateEvent(event) == 'left click':
            self.offset = event.scenePos() - self.scenePos()
        elif translateEvent(event) == 'right click':
            self.GM.pointMustDie(self.ref)

    def mouseReleaseEvent(self,event):
        if translateEvent(event) == 'left release':
            pos = event.scenePos() - self.offset # TODO:Check that!!
            self.GM.pointMustMove(self.ref, pos.x(), pos.y())
        
    def mouseMoveEvent(self,event):
        if translateEvent(event) == 'left move':
            pos = event.scenePos()
            self.setPos(pos - self.offset)

    def move(self,x, y):
        self.setPos(x,y)

    def removeFromScene(self):
        self.scene().removeItem(self)

class QGUILineEdit(QtWidgets.QLineEdit):
    def __init__(self, name, GM):
        QtWidgets.QLineEdit.__init__(self)
        self.name = name
        self.GM = GM
        self.editingFinished.connect(self.editHandler)

    def editHandler(self):
        self.GM.coordsMustChange(self.name, str(self.text()))

class CWin(QtWidgets.QWidget):
    def __init__(self, GM, GUI):
        # Creating window
        QtWidgets.QWidget.__init__(self)
        self.setWindowTitle('Graph scanner')

        self.GM = GM

        # Creating canvas
        self.canvas = Canvas(GM, self)

        # Creating buttons
        self.btn_help = QtWidgets.QPushButton("Help and commands",self)
        self.btn_help.clicked.connect(displayHelpMessage)

        self.btn_change_image = QtWidgets.QPushButton("Browse image",self)
        self.btn_change_image.clicked.connect(GUI.handleChangeImage)

        self.btn_quit = QtWidgets.QPushButton("Exit program",self)
        self.btn_quit.clicked.connect(GUI.handleQuit)

        self.btn_export =  QtWidgets.QPushButton("Export data to clipboard",self)
        self.btn_export.clicked.connect(GM.dataMustBeExported)

        # Button for development
        #self.btn_debug = QtWidgets.QPushButton("Load test image",self)
        #self.btn_debug.clicked.connect(GUI.loadTest)

        # Debuging label
        self.debug_label = QtWidgets.QLabel("Default text", self)

        # Coordinates
        self.coords_layout = QtWidgets.QGridLayout()
        self.label_x = QtWidgets.QLabel("X axis", self)
        self.label_y = QtWidgets.QLabel("Y axis", self)
        self.label_min = QtWidgets.QLabel("Min", self)
        self.label_min.setAlignment(QtCore.Qt.AlignHCenter)
        self.label_max = QtWidgets.QLabel("Max", self)
        self.label_max.setAlignment(QtCore.Qt.AlignHCenter)
        self.xmin = QGUILineEdit("xmin", GM = self.GM)
        self.xmax = QGUILineEdit("xmax", GM = self.GM)
        self.ymin = QGUILineEdit("ymin", GM = self.GM)
        self.ymax = QGUILineEdit("ymax", GM = self.GM)
        self.coords_layout.addWidget(self.label_min,0,1)
        self.coords_layout.addWidget(self.label_max,0,2)
        self.coords_layout.addWidget(self.label_x,1,0)
        self.coords_layout.addWidget(self.xmin,1,1)
        self.coords_layout.addWidget(self.xmax,1,2)
        self.coords_layout.addWidget(self.label_y,2,0)
        self.coords_layout.addWidget(self.ymin,2,1)
        self.coords_layout.addWidget(self.ymax,2,2)

        # Defining layout
        self.vbox = QtWidgets.QVBoxLayout()
        #self.vbox.addWidget(self.btn_debug)
        self.vbox.addWidget(self.btn_help)
        self.vbox.addWidget(self.btn_change_image)
        self.vbox.addWidget(self.canvas)
        self.vbox.addLayout(self.coords_layout)
        self.vbox.addWidget(self.btn_export)
        self.vbox.addWidget(self.btn_quit)
        self.vbox.addWidget(self.debug_label)

        # Setting layout and displaying window
        self.setLayout(self.vbox)
        self.show()

    def keyPressEvent(self, event):
        logging.debug("Key press event")
        if event.key() == QtCore.Qt.Key_Q and event.modifiers() == QtCore.Qt.ControlModifier:
            self.GM.GUI.handleQuit()

def getQtColor(user_color):
    if not QtGui.QColor.isValidColor(user_color):
        print("Invalid point color: %s" % user_color)
        user_color = black
    color_object = QtGui.QColor()
    color_object.setNamedColor(user_color)
    return color_object


class CGUI:
    def __init__(self, GM):
        self.GM = GM
        # Loading images (shared by several objects, like CGUIPoints)
        self.green_cross = QtGui.QPixmap(os.path.join(share_folder,'cursor_green2.png'))
        self.red_cross = QtGui.QPixmap(os.path.join(share_folder,'cursor.png'))
    
        # Configuration
        self.size_of_points = 1.
        user_width = GM.param_manager.param_dict["border_width"]
        try:
            user_width = int(user_width)
        except:
            print("Invalid border width, using default")
            user_width = 4
    
        self.pen_border_width = int(GM.param_manager.param_dict["border_width"])
        self.pen_point_width = 5
        self.win = CWin(self.GM, self)
        #self.border_thick_color = QtGui.QColor(0,0,0,70)
        self.border_thick_color = getQtColor(GM.param_manager.param_dict["thick_line_color"])
        self.border_thin_color = getQtColor(GM.param_manager.param_dict["thin_line_color"])
        self.border_thick_color.setAlpha(70)

    def handleChangeImage(self):
        filename = self.askChangeImage()
        if filename != None: # TODO: rather check that it's a valid file?
            self.GM.model.changeBackground(filename)

    def handleQuit(self):
        Qt.QApplication.quit()

    def loadTest(self):
        self.GM.model.changeBackground(os.path.join(share_folder, 'default.jpg'))

    def askChangeImage(self):
        confirm_message = QtWidgets.QMessageBox(text="Changing the image file will erase all points. Are you sure you want to continue?")
        confirm_message.addButton(QtWidgets.QMessageBox.Ok)
        confirm_message.addButton(QtWidgets.QMessageBox.Cancel)
        confirm_message.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        # FOR DEVEL PERIOD ONLY
        #confirm_status = confirm_message.exec_() # "exec" (without _) worked with python3
        confirm_status =  QtWidgets.QMessageBox.Ok
        if confirm_status == QtWidgets.QMessageBox.Ok:
            file_name, _ = QtWidgets.QFileDialog(parent=None,caption="Select the image file", directory='').getOpenFileName() # returns a tuple
        else:
            file_name = None

        return file_name

def translateEvent(event):
    """Turn a mouse event to a string. Using this function to deal with events greatly improves code readability.
    Examples:
    "ctrl + left click"
    "ctrl + wheel"
    """
    # Beware of the space chars at the end of the keys

    types = {
            'click': QtCore.QEvent.MouseButtonPress,
            'release':QtCore.QEvent.MouseButtonRelease,
            'move':QtCore.QEvent.MouseMove,
            'wheel':QtCore.QEvent.Wheel,
            'scene_click': QtCore.QEvent.GraphicsSceneMousePress,
            'scene_release': QtCore.QEvent.GraphicsSceneMouseRelease,
            'scene_move': QtCore.QEvent.GraphicsSceneMouseMove
            }

    modifiers = {
            '':QtCore.Qt.NoModifier,
            'ctrl + ':QtCore.Qt.ControlModifier,
            'alt + ':QtCore.Qt.AltModifier,
            'shift + ':QtCore.Qt.ShiftModifier } # TODO: combinations of several modifiers

    buttons = {
            "left ":QtCore.Qt.LeftButton,
            "right ":QtCore.Qt.RightButton,
            "middle ":QtCore.Qt.MiddleButton }

    my_type = getDictKeyFromItem(types, event.type())
    if my_type != None and my_type[:6] == 'scene_':
        my_type = my_type[6:] # ugly thing I have to do because a QGraphicsScene click is not a QGraphicsView click...
    my_modifiers = getDictKeyFromItem(modifiers, event.modifiers())

    if my_type == 'wheel':        my_buttons = ''
    elif my_type == 'release':     my_buttons = getDictKeyFromItem(buttons, event.button())
    else:            my_buttons = getDictKeyFromItem(buttons, event.buttons())

    string = "%s%s%s" % (my_modifiers, my_buttons, my_type)

    return string

def getDictKeyFromItem(mydict, item_searched):
    for key, item in mydict.items():
        if item == item_searched:
            return key
    return None

class Canvas(QtWidgets.QGraphicsView):
    def __init__(self, GM, parent_win):
        QtWidgets.QGraphicsView.__init__(self, parent_win)
        self.scene = QtWidgets.QGraphicsScene()
        self.setScene(self.scene)
        self.background_item = None
        self.borders = None
        self.GM = GM

    def clearBackground(self):
        self.scene.removeItem(self.background_item)
        self.background_item = None

    def fitBackgroundWithBorders(self):
        # adjusting borders
        xmin = 0
        xmax = self.background_pixmap.width()
        ymin = 0
        ymax = self.background_pixmap.height()
        self.GM.bordersMustChange('xmin', xmin)
        self.GM.bordersMustChange('xmax', xmax)
        self.GM.bordersMustChange('ymin', ymin)
        self.GM.bordersMustChange('ymax', ymax)
        self.setSceneRect(self.scene.itemsBoundingRect())

    def setBackground(self, filename):
        if self.background_item != None:
            self.clearBackground()
        self.background_pixmap =  QtGui.QPixmap(filename)
        self.background_item = self.scene.addPixmap(self.background_pixmap)

        # centering the image
        self.centerOn(self.background_item)
        self.fitInView(self.background_item, QtCore.Qt.KeepAspectRatio)

        # If borders have not been created yet, create them
        if self.borders is None:
            self.borders = CBorders(self.GM)
        self.fitBackgroundWithBorders()
        
        # the sceneRect never shrinks on its own, we have to do it ourselves
        # shrink it AFTER the borders have been ajusted!
        self.setSceneRect(self.scene.itemsBoundingRect())

    def rescaleCanvas(self, delta):
        factor = 1.2
        if delta < 0:
            factor = 1.0 / factor
        logging.debug("Zooming in or out")
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.scale(factor, factor)

    def rescalePointsAndBorders(self, delta):
        factor = 1.2
        if delta < 0:
            factor = 1.0 / factor
        self.GM.GUI.size_of_points *= factor
        logging.debug("Scaling points")
        for ref in self.GM.dict_of_points:
            self.GM.dict_of_points[ref].setScale(self.GM.GUI.size_of_points)

        self.GM.GUI.win.canvas.borders.changeWidth(self.GM.GUI.size_of_points*self.GM.GUI.pen_border_width)

    def mousePressEvent(self, event):
        pos_in_scene = self.mapToScene(event.pos())
        if translateEvent(event) == 'ctrl + left click':
            self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
            self.scene_offset = self.mapToScene(event.pos())
        elif translateEvent(event) == 'left click' and self.scene.itemAt(pos_in_scene, QtGui.QTransform()) == self.background_item:
            pos_x = pos_in_scene.x()
            pos_y = pos_in_scene.y()
            self.GM.model.addPoint(pos_x, pos_y)

        else:
            QtWidgets.QGraphicsView.mousePressEvent(self,event)
            logging.debug("Calling built-in QGraphicsView.mousePressEvent")

    def mouseMoveEvent(self, event):
        self.GM.GUI.win.debug_label.setText("Moving at %d, %d" % (event.pos().x(), event.pos().y() ) )
        if translateEvent(event) == 'ctrl + left move':
            translate_by = self.mapToScene(event.pos()) - self.scene_offset
            self.translate(translate_by.x(), translate_by.y())
        else:
            QtWidgets.QGraphicsView.mouseMoveEvent(self,event)

    def mouseReleaseEvent(self, event):
        if translateEvent(event) == 'ctrl + left release':
            self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        else:
            QtWidgets.QGraphicsView.mouseReleaseEvent(self,event)

    def wheelEvent(self, event):
        if translateEvent(event) == 'ctrl + wheel': # zoom the canvas in or out
            delta = event.angleDelta().y()
            self.rescaleCanvas(delta)
        elif translateEvent(event) == 'alt + wheel': # zoom the points and borders
            delta = event.angleDelta().x() # it seems alt + scroll emulates a horizontal scroll
            self.rescalePointsAndBorders(delta)
        else:
            QtWidgets.QGraphicsView.wheelEvent(self,event)

class CBorderLine(QtWidgets.QGraphicsItemGroup):
    def __init__(self, border_type, GM):
        self.GM = GM
        QtWidgets.QGraphicsItemGroup.__init__(self, parent = None)
        self.thick_line = QtWidgets.QGraphicsLineItem(1,2,3,4)
        self.thin_line = QtWidgets.QGraphicsLineItem(1,2,3,4)
        self.addToGroup(self.thin_line)
        self.addToGroup(self.thick_line)
        self.GM.GUI.win.canvas.scene.addItem(self)
        self.setZValue(0.5)

        self.factor = 9
        self.thin_pen = QPen(self.GM.GUI.border_thin_color, GM.GUI.pen_border_width)
        self.thick_pen = QPen(self.GM.GUI.border_thick_color, GM.GUI.pen_border_width*self.factor)
        self.thin_line.setPen(self.thin_pen)
        self.thick_line.setPen(self.thick_pen)

        self.border_type = border_type
        self.GM = GM
    
    def mouseMoveEvent(self, event):
        translate_by_x = event.scenePos().x() - self.scenePos().x()
        translate_by_y = event.scenePos().y() - self.scenePos().y()
        if self.border_type in [ 'xmin', 'xmax']:
            x1 = event.scenePos().x()
            x2 = x1
            y1 = self.thin_line.line().y1()
            y2 = self.thin_line.line().y2()
        elif self.border_type in ['ymin', 'ymax']:
            x1 = self.thin_line.line().x1()
            x2 = self.thin_line.line().x2()
            y1 = event.scenePos().y()
            y2 = y1
        self.setLine( x1, y1, x2, y2)

    def mousePressEvent(self, event):
        # Reimplementing this method is necessary, because default implem calls ignore()
        pass

    def mouseReleaseEvent(self, event):
        if self.border_type in [ 'xmin', 'xmax']:
            border_value = event.scenePos().x()
        elif self.border_type in ['ymin', 'ymax']:
            border_value = event.scenePos().y()
        self.GM.bordersMustChange(self.border_type, border_value)

    def setLine(self,x1,y1,x2,y2):
        self.thin_line.setLine(x1,y1,x2,y2)
        self.thick_line.setLine(x1,y1,x2,y2)
        self.thin_line.setZValue(0.6)
        self.thick_line.setZValue(0.4)


class CBorders:
    def __init__(self, GM):
        self.border_lines = {}
    #    self.pen = QPen(self.GM.GUI.border_thick_color, GM.GUI.pen_border_width)
        self.GM = GM
        self.width_factor = 3

        for name in [ 'xmin', 'xmax', 'ymin', 'ymax']:
            current_border = CBorderLine(name, GM = self.GM)
            self.border_lines[name] = current_border

    def changeWidth(self, new_width):
        thin_pen = QPen(self.GM.GUI.border_thin_color, new_width)
        thick_pen = QPen(self.GM.GUI.border_thick_color, new_width*self.width_factor)
        logging.debug("size of points: %s" % self.GM.GUI.size_of_points)
        for name in self.border_lines:
            self.border_lines[name].thick_line.setPen(thick_pen)
            #self.border_lines[name].thin_line.setPen(thin_pen)

    def resizeRect(self, xmin, xmax, ymin, ymax): # in scene coordinates
        #print("Resizing rect : %d, %d, %d, %d" %(xmin, xmax, ymin, ymax) )
        self.border_lines['xmin'].setLine(xmin, ymin, xmin, ymax)
        self.border_lines['xmax'].setLine(xmax, ymin, xmax, ymax)
        self.border_lines['ymin'].setLine(xmin, ymin, xmax, ymin)
        self.border_lines['ymax'].setLine(xmin, ymax, xmax, ymax)

###
# THE MAIN
###
    
app = Qt.QApplication(sys.argv)
myapp = CGUIManager()
#myapp = CApplication()

if __name__ == "__main__":
    sys.exit(app.exec_())

##TODO##

    #BUGS
        # help button won't work on some platforms?

    #IMPROVEMENTS
        # keyboard shortcuts (quit, export, etc.)
        # set lines as centered around zero, and use setPos instead of changing line coordinates
        # User input checkings must occur in the model (and throw an exception that sends the user a graphical message), not directly in the GUI!
        # Use inkscape's code for rectangle resizing?
        # Improve the help pages (add css, add images, give the location of the config file, make the color list available offline, etc.)


    # MISSING FEATURES
        # allow changes in keyboard shortcuts and mouse behaviors?
        # Thin dashed-line outsite the rectangle to ease alignment
        # How can I display the unclickable area outside of the image in the canvas?
        # Import image from clipboard
        # export data to file (and not only clipboard)
        # ability to rotate the background image
        # a check box to decide whether to sort the points (xy graph), or not (parametric graph)
        # ability to draw lines between the points (to see if the sampling is good enough, and to check that points are in the right order in parametric mode
