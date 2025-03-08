import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene

from PyQt6 import uic  # For loading .ui files dynamically
from PyQt6.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch
import pandas as pd

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

    def display_overlayed_image(self, input_image, overlay_image):
        """
        Display an overlayed image.
        Args:
            input_image (np.ndarray): The input image.
            overlay_image (np.ndarray): The image to overlay.
        """
        self.ax.clear()  # Clear any existing content
        self.ax.imshow(input_image, cmap='gray', aspect='auto')  # Plot the input image
        self.ax.imshow(overlay_image, alpha=0.5, aspect='auto', cmap='seismic')  # Plot the overlay image
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



        #init variables
        self.batch_index = -1
        self.img_index = 0

        self.set_image_labels()
        



        # init UI
        # Add image canvas to layout
        self.canvas = ImageCanvas(self, width=5, height=4, dpi=100)
        self.horizontalLayout.addWidget(self.canvas)

        # Disable interactive elements until dataframe is loaded
        self.set_interactive_elements_enabled(False)

        # Connect the button
        # self.pushButton.clicked.connect(self.on_button_click)
        self.pushButton_2.clicked.connect(self.clear_button_click)
        self.loadBatchButton.clicked.connect(self.load_batch_click)
        self.nextButton.clicked.connect(self.next_image_click)
        self.prevButton.clicked.connect(self.prev_image_click)
        self.dummyLoadButton.clicked.connect(self.dummy_load_image)
        self.ThresholdSlider_1.valueChanged.connect(self.slider_value_changed)


        # Start polling for dataframe
        self.start_dataframe_loading()


    def set_interactive_elements_enabled(self, enabled: bool):
        """Enable or disable all interactive elements."""
        self.pushButton_2.setEnabled(enabled)
        self.loadBatchButton.setEnabled(enabled)
        self.nextButton.setEnabled(enabled)
        self.prevButton.setEnabled(enabled)
        self.dummyLoadButton.setEnabled(enabled)
        self.ThresholdSlider_1.setEnabled(enabled)

    def start_dataframe_loading(self):
        """ Periodically check if dataframe is ready """
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_dataframe)
        self.timer.start(2000)  # Check every 2 seconds

    def check_dataframe(self):
        """ Fetch dataframe if available and stop timer once received """
        df = self.conn.get_dataframe()
        if df is not None:
            self.stats_dataframe = pd.read_json(df)
            self.timer.stop()  # Stop checking

            # Enable interactive elements
            self.set_interactive_elements_enabled(True)

            self.dataframeLabel.setText("Dataframe: Loaded!")

            # timeout for 5 seconds before clearing the label
            QTimer.singleShot(5000, lambda: self.dataframeLabel.clear())



    def set_image_labels(self):
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

        self.set_image_labels()


    def load_batch_click(self):
        self.batch_index += 1
        self.img_index = 0
        image = self.conn.get_image(self.batch_index, self.img_index)
        self.canvas.display_image(np.array(image)[0])


        self.set_image_labels()


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

        self.set_image_labels()


    def prev_image_click(self):
        if self.img_index == 0:
            self.img_index = 31
            # use the cache
        else:
            self.img_index -= 1
        image = self.conn.get_image(self.batch_index, self.img_index)
        self.canvas.display_image(np.array(image)[0])

        self.set_image_labels()


    def dummy_load_image(self):
        self.input_image = torch.load("data/input_image.pt").numpy()
        self.uncertainty_image = torch.load("data/entropy.pt").numpy()

        
        self.canvas.display_overlayed_image(self.input_image, self.uncertainty_image)


    def slider_value_changed(self, value):
        """
        Handle the slider change event .
        Args:
            value (int): The new value of the slider.
        """

        def map_value(value, in_min, in_max, out_min, out_max):
            """Linearly maps a value from one range to another."""
            return out_min + (float(value - in_min) / (in_max - in_min)) * (out_max - out_min)

        # Map the slider value to the range of the entropy values
        min_entropy = self.uncertainty_image.min()
        max_entropy = self.uncertainty_image.max()
        threshold = map_value(value, 0, 100, min_entropy, max_entropy)


        # threshold the uncertainty image
        thresholded_image = self.threshold_image(self.uncertainty_image, threshold)

        # Display the thresholded image overlayed on the input image
        self.canvas.display_overlayed_image(self.input_image, thresholded_image)



    def threshold_image(self, image, threshold):
        """
        Threshold an image.
        Args:
            image (np.ndarray): The image to threshold.
            threshold (float): The threshold value.
        Returns:
            np.ndarray: The thresholded image.
        """
        thresholded_image = np.where(image > threshold, image, 0)
        return thresholded_image

        
        


    def closeEvent(self, event):
        self.conn.close_connection()
        return super().closeEvent(event)
    
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())