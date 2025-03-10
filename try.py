import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QHeaderView

from PyQt6 import uic  # For loading .ui files dynamically
from PyQt6.QtCore import QTimer, QSortFilterProxyModel, pyqtSignal, QModelIndex
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch
import pandas as pd
from ServerConnection import ServerConnection
from PyQt6.QtCore import Qt, QAbstractTableModel
import pandas as pd

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableView, QPushButton, QMessageBox
from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex
import pandas as pd


class DataFrameDialog(QDialog):
    row_selected = pyqtSignal(list,list)  # Signal to send selected row data

    def __init__(self, dataframe, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DataFrame Viewer")
        self.resize(500, 300)

        # Layout
        layout = QVBoxLayout(self)

        # Create QTableView
        self.table_view = QTableView(self)
        self.model = DataFrameModel(dataframe)
        self.proxy_model = QSortFilterProxyModel(self)  # Sorting model
        self.proxy_model.setSourceModel(self.model)

        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)

        # Connect double-click event
        self.table_view.doubleClicked.connect(self.row_double_clicked)


        # Add widgets to layout
        layout.addWidget(self.table_view)
        


    def row_double_clicked(self, index: QModelIndex):
        """ Emit the selected row along with correctly sorted surrounding rows """

        # Get the correct row in the sorted view
        sorted_row_idx = index.row()  
        source_index = self.proxy_model.mapToSource(index)  # Convert to original index
        original_row_idx = source_index.row()  # Get correct row index

        # Get first and last visible row in sorted order
        first_visible_sorted = self.table_view.indexAt(self.table_view.rect().topLeft()).row()
        last_visible_sorted = self.table_view.indexAt(self.table_view.rect().bottomLeft()).row()

        if last_visible_sorted == -1:  # If last row isn't fully visible, adjust
            last_visible_sorted = self.proxy_model.rowCount() - 1

        # Define the window of rows (±2 rows around selected)
        window_size = 2
        start_sorted_idx = max(first_visible_sorted, sorted_row_idx - window_size)
        end_sorted_idx = min(last_visible_sorted, sorted_row_idx + window_size)

        # Convert sorted indices to original dataframe indices
        surrounding_rows = []
        for i in range(start_sorted_idx, end_sorted_idx + 1):
            source_row = self.proxy_model.mapToSource(self.proxy_model.index(i, 0)).row()  # Get original row
            row_data = [self.model.data(self.model.index(source_row, col)) for col in range(self.model.columnCount())]
            surrounding_rows.append(row_data)

        # Get selected row data
        selected_row_data = [self.model.data(self.model.index(original_row_idx, col)) for col in range(self.model.columnCount())]

        # Emit both selected and surrounding rows
        self.row_selected.emit(selected_row_data, surrounding_rows)

    def get_window_rows_data(self):
        """ Get the data of a window of rows around the selected row """
        selected_row = self.table_view.selectedIndexes()[0].row()
        window_size = 5  # Number of rows to show around the selected row




class DataFrameModel(QAbstractTableModel):
    def __init__(self, dataframe=pd.DataFrame(), parent=None):
        super().__init__(parent)
        self.dataframe = dataframe

    def rowCount(self, parent=None):
        return self.dataframe.shape[0]

    def columnCount(self, parent=None):
        return self.dataframe.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self.dataframe.iloc[index.row(), index.column()])
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.dataframe.columns[section])  # Column names
            elif orientation == Qt.Orientation.Vertical:
                return str(self.dataframe.index[section])  # Row index
        return None



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
        # Define a custom colormap for overlayed image with RGBA values
        
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
        self.canvas_1 = ImageCanvas(self, width=7, height=6, dpi=100)
        self.canvas_2 = ImageCanvas(self, width=7, height=6, dpi=100)

        self.horizontalLayout_1.addWidget(self.canvas_1)
        self.horizontalLayout_2.addWidget(self.canvas_2)

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
            self.show_dataframe_popup(self.stats_dataframe)


    def show_dataframe_popup(self, df):
        """ Open the popup window to display the dataframe """
        self.dialog = DataFrameDialog(df, self)
        self.dialog.row_selected.connect(self.handle_selected_row_window)  # Connect signal
        self.dialog.show()  # Show as modal popup

    # def handle_selected_row(self, row_data):
    #     """ Handle the selected row received from DataFrameDialog """
    #     print("Row selected in popup:", row_data)


    
    def handle_selected_row_window(self, selected_row, surrounding_rows):
        """ Handle the selected row and its surrounding rows """
        print("Selected Row:", selected_row)
        print("Surrounding Rows:", surrounding_rows)




    def set_image_labels(self):
        if self.batch_index == -1:
            self.batchLabel.setText("Batch: None")
            self.imageLabel.setText("Image: None")
            return
        self.batchLabel.setText(f"Batch: {self.batch_index}")
        self.imageLabel.setText(f"Image: {self.img_index}")



    def on_button_click(self):
        image = self.conn.get_image(self.batch_index, self.img_index)

        self.canvas_1.display_image(np.array(image)[0])
        self.canvas_2.display_image(np.array(image)[0])

    def clear_button_click(self):
        self.canvas_1.ax.clear()
        self.canvas_1.ax.axis('off')
        self.canvas_1.draw()

        self.canvas_2.ax.clear()
        self.canvas_2.ax.axis('off')
        self.canvas_2.draw()

        self.batch_index = -1
        self.img_index = 0

        self.set_image_labels()


    def get_images(self, indices):
        pass




    def load_batch_click(self):
        self.batch_index = 3
        self.img_index = 4
        # put batch_index and img_index in a tuple
        indices = [(self.batch_index, self.img_index)]
        images_df = pd.read_json(self.conn.get_images(indices))
        image_data = images_df[(images_df["batch_index"] == self.batch_index)
                                 & (images_df["image_index"] == self.img_index)]
        self.input_image = np.array(image_data["input_image"].values[0])
        self.uncertainty_image = np.array(image_data["entropy_image"].values[0])
        self.canvas_1.display_overlayed_image(self.input_image, self.uncertainty_image)


        self.set_image_labels()





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

        
        self.canvas_1.display_overlayed_image(self.input_image, self.uncertainty_image)
        self.canvas_2.display_overlayed_image(self.input_image, self.uncertainty_image)


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
        self.canvas_1.display_overlayed_image(self.input_image, thresholded_image)



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