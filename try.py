import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene
from PyQt6.QtWidgets import QFileDialog

from PyQt6 import uic  # For loading .ui files dynamically
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from ServerConnection import ServerConnection


class ImageCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        self.ax.axis('off')
        super().__init__(fig)
        self.setParent(parent)

    def display_image(self, image_array):
        """
        Display an image stored as a NumPy array.
        Args:
            image_array (np.ndarray): The image to display.
        """
        self.ax.clear()  # Clear any existing content
        self.ax.imshow(image_array, cmap='gray', aspect='auto')  # Plot the image
        self.ax.axis('off')  # Turn off axis
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load the .ui file
        uic.loadUi("form.ui", self)  # Replace with your .ui file path

        # Create a connection to the server
        self.conn = ServerConnection()
        self.conn.open_connection()

        # Load dataframe
        # self.dataframe = self.conn.get_dataframe()

        #init variables
        self.batch_index = -1
        self.img_index = 0

        self.set_labels()


        #TODO: Create an API that queries the server for dataframe with ranked images and their entopy values


        # init UI
        # Add image canvas to layout
        self.canvas = ImageCanvas(self, width=5, height=4, dpi=100)
        self.horizontalLayout.addWidget(self.canvas)

        # Connect the button
        # self.pushButton.clicked.connect(self.on_button_click)
        self.pushButton_2.clicked.connect(self.clear_button_click)
        self.loadBatchButton.clicked.connect(self.load_batch_click)
        self.nextButton.clicked.connect(self.next_image_click)
        self.prevButton.clicked.connect(self.prev_image_click)



    def set_labels(self):
        if self.batch_index == -1:
            self.batchLabel.setText("Batch: None")
            self.imageLabel.setText("Image: None")
            return
        self.batchLabel.setText(f"Batch: {self.batch_index}")
        self.imageLabel.setText(f"Image: {self.img_index}")

    def on_button_click(self):
        image = self.conn.get_image(self.batch_index, self.img_index)

        self.canvas.display_image(np.array(image)[0])

    def clear_button_click(self):
        self.canvas.ax.clear()
        self.canvas.ax.axis('off')
        self.canvas.draw()
        self.batch_index = -1
        self.img_index = 0

        self.set_labels()


    def load_batch_click(self):
        self.batch_index += 1
        self.img_index = 0
        image = self.conn.get_image(self.batch_index, self.img_index)
        self.canvas.display_image(np.array(image)[0])


        self.set_labels()


    def load_dataframe_click(self):
        pass



    def next_image_click(self):
        if self.img_index == 31:
            self.img_index = 0
            # use the cache
        else:
            self.img_index += 1
        image = self.conn.get_image(self.batch_index, self.img_index)
        self.canvas.display_image(np.array(image)[0])

        self.set_labels()


    def prev_image_click(self):
        if self.img_index == 0:
            self.img_index = 31
            # use the cache
        else:
            self.img_index -= 1
        image = self.conn.get_image(self.batch_index, self.img_index)
        self.canvas.display_image(np.array(image)[0])

        self.set_labels()

        
        


    def closeEvent(self, event):
        self.conn.close_connection()
        return super().closeEvent(event)
    
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())