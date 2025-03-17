import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6 import uic
from PyQt6.QtCore import QTimer, QSortFilterProxyModel, pyqtSignal, QModelIndex, QVariant
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import torch
import pandas as pd
from ServerConnection import ServerConnection
from PyQt6.QtCore import Qt, QAbstractTableModel
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableView, QPushButton, QMessageBox
from torchmetrics.functional import precision_recall_curve
from sklearn.metrics import average_precision_score



class CustomSortFilterProxyModel(QSortFilterProxyModel):
    def lessThan(self, left_index, right_index):
        """ Ensure numbers are sorted numerically, strings alphabetically, and booleans correctly. """
        left_data = left_index.data(Qt.ItemDataRole.EditRole)
        right_data = right_index.data(Qt.ItemDataRole.EditRole)

        # Handle None or empty values
        if left_data is None or left_data == "":
            return True
        if right_data is None or right_data == "":
            return False

        # Convert NumPy types to standard Python types
        left_data = self.convert_type(left_data)
        right_data = self.convert_type(right_data)

        return left_data < right_data  # Compare correctly

    def convert_type(self, value):
        """ Convert NumPy data types to standard Python types for proper sorting """
        if isinstance(value, (np.int64, np.int32, np.int16, np.int8)):
            return int(value)
        elif isinstance(value, (np.float64, np.float32, np.float16)):
            return float(value)
        elif isinstance(value, (np.bool_, bool)):
            return bool(value)
        elif isinstance(value, str):
            return value.strip()  # Ensure no whitespace issues
        return value  # Fallback

class DataFrameDialog(QDialog):
    """ Dialog to display server data in a QTableView. """

    # Signals to communicate with MainWindow
    row_selected = pyqtSignal(list) 
    load_batch_signal = pyqtSignal(list)  
    load_selected_images_signal = pyqtSignal(list)  

    def __init__(self, dataframe, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Data")
        self.resize(500,300)

        self.last_loaded_index = 0 

        layout = QVBoxLayout(self)

        # Create QTableView
        self.table_view = QTableView(self)
        self.model = DataFrameModel(dataframe)
        
        # Use the CustomSortFilterProxyModel for proper sorting
        self.proxy_model = CustomSortFilterProxyModel(self)  
        self.proxy_model.setSourceModel(self.model)

        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)

        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)  # Select entire rows
        self.table_view.setSelectionMode(QTableView.SelectionMode.MultiSelection)  # Allow multiple row selection


        # Connect sorting changes to reset tracking
        self.proxy_model.layoutChanged.connect(self.reset_batch_loading)

        # Connect double-click event
        self.table_view.doubleClicked.connect(self.row_double_clicked)

        # Add load next batch button
        self.loadBatchButton = QPushButton("Load Next Batch", self)
        self.loadBatchButton.clicked.connect(self.load_next_batch_clicked)

        # Add load selected button
        self.loadSelectedButton = QPushButton("Load Selected Images")  # New button
        self.loadSelectedButton.clicked.connect(self.load_selected_images)

        # Add widgets to layout
        layout.addWidget(self.table_view)
        
        layout.addWidget(self.loadBatchButton)
        layout.addWidget(self.loadSelectedButton)   

        # Ensure the dialog stays on top when clicked
        self.setWindowFlags(Qt.WindowType.Window)
        

    def reset_batch_loading(self):
        """ Reset batch tracking when sorting changes. """
        self.last_loaded_index = 0

    def load_next_batch_clicked(self):
        """ Load the next 10 images from the currently sorted view of server data. """
        total_rows = self.proxy_model.rowCount()
        if self.last_loaded_index >= total_rows:
            QMessageBox.information(self, "Info", "All images in the current view are already loaded.")
            return

        batch_size = 10
        indices_to_load = []

        for i in range(self.last_loaded_index, min(self.last_loaded_index + batch_size, total_rows)):
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(i, 0))
            row_idx = source_index.row()

            batch_index = self.model.data(self.model.index(row_idx, self.model.dataframe.columns.get_loc("batch_index")), Qt.ItemDataRole.EditRole)
            image_index = self.model.data(self.model.index(row_idx, self.model.dataframe.columns.get_loc("image_index")), Qt.ItemDataRole.EditRole)

            indices_to_load.append((int(batch_index), int(image_index)))

        # Update the last loaded index
        self.last_loaded_index += batch_size

        # Emit signal to MainWindow to load these images
        self.load_batch_signal.emit(indices_to_load)

    
    def load_selected_images(self):
        """ Load images from selected rows in the current sorted view of server data."""
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.information(self, "Info", "No rows selected.")
            return

        indices_to_load = []

        for index in selected_indexes:
            source_index = self.proxy_model.mapToSource(index)  # Convert sorted index to original
            row_idx = source_index.row()

            batch_index = self.model.data(self.model.index(row_idx, self.model.dataframe.columns.get_loc("batch_index")), Qt.ItemDataRole.EditRole)
            image_index = self.model.data(self.model.index(row_idx, self.model.dataframe.columns.get_loc("image_index")), Qt.ItemDataRole.EditRole)

            indices_to_load.append((int(batch_index), int(image_index)))

        # Emit signal to MainWindow to load the selected images
        self.load_selected_images_signal.emit(indices_to_load)
        


    def row_double_clicked(self, index: QModelIndex):
        """ Emit the selected row along with correctly sorted surrounding rows """

        # Get the correct row in the sorted view
        source_index = self.proxy_model.mapToSource(index)  # Convert to original index
        original_row_idx = source_index.row()  # Get correct row index

        # Get selected row data
        selected_row_data = [self.model.data(self.model.index(original_row_idx, col)) for col in range(self.model.columnCount())]

        # Emit both selected and surrounding rows
        self.row_selected.emit(selected_row_data)





class DataFrameModel(QAbstractTableModel):
    def __init__(self, dataframe=pd.DataFrame(), parent=None):
        super().__init__(parent)
        self.dataframe = dataframe

    def rowCount(self, parent=None):
        return self.dataframe.shape[0]

    def columnCount(self, parent=None):
        return self.dataframe.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """ Preserve datatype for sorting, but format properly for display """
        if not index.isValid():
            return QVariant()

        value = self.dataframe.iloc[index.row(), index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
                    # Format floats to 3 decimal places while preserving non-floats
            if isinstance(value, (float, np.float32, np.float64)):
                return f"{value:.3f}"
            return str(value)  # Display values as strings in the UI

        if role == Qt.ItemDataRole.EditRole:
            return value  # Preserve original datatype for internal logic

        return QVariant()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self.dataframe.columns[section])  # Column names
            elif orientation == Qt.Orientation.Vertical:
                return str(self.dataframe.index[section])  # Row index
        return QVariant()


    def update_data(self, new_dataframe):
        """ Update the dataframe and refresh the table view """
        self.beginResetModel()
        self.dataframe = new_dataframe
        self.endResetModel()

class MplCanvas(FigureCanvas):
    """ FigureCanvas for plotting Matplotlib plots """
    def __init__(self,parent=None, width=7, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)


        super().__init__(fig)
        self.setParent(parent)

    def plot(self, x, y, xlabel, ylabel):
        self.ax.clear()
        self.ax.plot(x, y)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.draw()


class ImageCanvas(FigureCanvas):
    """ FigureCanvas for displaying images as Matplotlib plots """
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
        self.ax.axis('off')
        super().__init__(fig)
        self.setParent(parent)
        self.binary = False

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
        Display an overlayed image with transparency, applying binarization if enabled.
        
        Args:
            input_image (np.ndarray): The input image.
            overlay_image (np.ndarray): The entropy image to overlay.
        """
        self.ax.clear()  # Clear any existing content
        self.ax.imshow(input_image, cmap='gray', aspect='auto')  # Plot the input image

        threshold = 0.1  # Default threshold for transparency

        if self.binary:
            binarized_overlay = (overlay_image > threshold).astype(np.uint8)

            # Show overlay as a single color instead of a colormap
            overlay_rgba = np.zeros((*binarized_overlay.shape, 4))  # Create an RGBA array
            overlay_rgba[binarized_overlay == 1] = [1, 1, 0, 0.6]  # Yellow color with transparency

        else:
            # Normalize overlay image for colormap
            norm = mcolors.Normalize(vmin=np.min(overlay_image), vmax=np.max(overlay_image))
            
            # Get the seismic colormap
            cmap = cm.get_cmap('seismic')
            
            # Apply colormap to the normalized overlay image
            overlay_rgba = cmap(norm(overlay_image))  # Converts to RGBA

            # Make values below threshold transparent
            overlay_rgba[overlay_image < threshold, 3] = 0  # Set alpha to 0 for low entropy values

        # Plot the overlay image
        self.ax.imshow(overlay_rgba, aspect='auto')
        self.ax.axis('off')  # Turn off axis
        self.draw()

class LoadedImagesFilterProxyModel(QSortFilterProxyModel):
    def filterAcceptsRow(self, source_row, source_parent):
        """ Only show rows where IsLoaded is True """
        index = self.sourceModel().index(source_row, self.sourceModel().dataframe.columns.get_loc("IsLoaded"))
        value = index.data(Qt.ItemDataRole.EditRole)
        return bool(value)  # Show row only if IsLoaded is True



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load the .ui file
        uic.loadUi("form-2.ui", self) # Load the UI file
        self.showMaximized()

        # Create a connection to the server
        self.conn = ServerConnection()
        self.conn.open_connection()

        self.images_df = pd.DataFrame()
        

        self.imagesTable.setSortingEnabled(True)  # Enable sorting for loaded images table

        # Create a model for stats_dataframe
        self.stats_model = DataFrameModel(pd.DataFrame())  
        self.proxy_model = LoadedImagesFilterProxyModel(self)  # Use custom filter
        self.proxy_model.setSourceModel(self.stats_model)

        self.imagesTable.setModel(self.proxy_model)
        self.imagesTable.doubleClicked.connect(self.on_image_table_double_click)
        self.imagesTable.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)  # Select entire rows

    

        # init UI
    
        # Add plot canvas to layout
        self.plotCanvas = MplCanvas(self, dpi=100)
        
        self.plotLayout.addWidget(self.plotCanvas, alignment=Qt.AlignmentFlag.AlignCenter)     


        # Add image canvas to layout
        self.canvas_1 = ImageCanvas(self, dpi=100)
        self.canvas_2 = ImageCanvas(self, dpi=100)

        self.horizontalLayout_1.addWidget(self.canvas_1)
        self.horizontalLayout_2.addWidget(self.canvas_2)

        # Disable interactive elements until dataframe is loaded
        self.set_interactive_elements_enabled(False)

        self.current_image_idx = None #the index in self.images_df of the currently selected/displayed image

        # Connect the buttons to their respective functions
        self.pushButton_2.clicked.connect(self.clear_button_click)

        self.nextButton.clicked.connect(self.next_image_click)
        self.prevButton.clicked.connect(self.prev_image_click)


        # Connect the sliders to their respective functions
        self.ThresholdSlider_1.valueChanged.connect(self.slider_value_changed)
        self.ThresholdSlider_2.valueChanged.connect(self.slider_value_changed)

        # Connect the dropdowns to their respective functions
        self.ComboBoxBackground1.currentTextChanged.connect(lambda: self.dropdown_change(column = self.ComboBoxBackground1.currentText(),canvas = 1))
        self.ComboBoxBackground2.currentTextChanged.connect(lambda: self.dropdown_change(self.ComboBoxBackground2.currentText(),2))
        self.ComboBoxForeground1.currentTextChanged.connect(lambda: self.dropdown_change(self.ComboBoxForeground1.currentText(),1))
        self.ComboBoxForeground2.currentTextChanged.connect(lambda: self.dropdown_change(self.ComboBoxForeground2.currentText(),2))

        # Connect the checkboxes to their respective functions
        self.checkBoxBinarize1.checkStateChanged.connect(self.onCheckboxChange)
        self.checkBoxBinarize2.checkStateChanged.connect(self.onCheckboxChange)

        # self.setup_statistics_ui()


        # Start polling for dataframe
        self.stats_dataframe = None
        self.start_dataframe_loading()


    def update_statistics(self):
        """ Update the statistics displayed in the UI. """
        if self.current_image_idx is None:
            return
        
        entropy_image = self.map_metric_to_image("Entropy", self.current_image_idx)
        error_mask = self.map_metric_to_image("Error Mask", self.current_image_idx)

        # Compute the best threshold and F1 score
        best_threshold, f1_score, precision, recall = self.compute_best_threshold(entropy_image, error_mask)
        self.entropyF1ScoreLabel.setText(f"F1 Score: {f1_score:.2f}")
        self.bestEntropyThresholdLabel.setText(f"Best Threshold: {best_threshold:.2f}")
        self.entropyAUPRLabel.setText(f"AUPR: {self.compute_aupr(entropy_image, error_mask):.2f}")

        # Plot the precision-recall curve
        self.plotCanvas.plot(recall, precision, "Recall", "Precision")

        
        

    def compute_aupr(self, uncertainty: np.ndarray, error_mask: np.ndarray) -> float:
        """Compute Area Under the Precision-Recall Curve (AUPR) for uncertainty as an error predictor."""
        return average_precision_score(error_mask.flatten(), uncertainty.flatten())

    
    def compute_best_threshold(self, uncertainty_image, error_mask):
        """ Compute the best threshold for the given image and target. """
        # Convert the images to tensors
        uncertainty_image = torch.tensor(uncertainty_image)
        error_mask = torch.tensor(error_mask)

        # Flatten the error mask and entropy tensor
        error_mask_flat = error_mask.flatten()
        uncertainty_image_flat = uncertainty_image.flatten()

        # Calculate precision and recall for different thresholds
        precision, recall, thresholds = precision_recall_curve(uncertainty_image_flat, error_mask_flat, task='binary')

        # Calculate F1 score for each threshold
        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-10)

        # Get the index of the best threshold (highest F1 score)
        best_threshold_idx = f1_scores.argmax()
        best_threshold = thresholds[best_threshold_idx]

        return best_threshold, f1_scores[best_threshold_idx], precision, recall



    def onCheckboxChange(self, state):
        """ Handle checkbox state change and apply binarization if checked. """
        sender = self.sender()  # Get the checkbox that triggered the event
        canvas = None

        if sender == self.checkBoxBinarize1:
            self.canvas_1.binary = state == Qt.CheckState.Checked  # Update binarization state
            foreground_metric = self.ComboBoxForeground1.currentText()
            background_metric = self.ComboBoxBackground1.currentText()
            canvas = self.canvas_1
        elif sender == self.checkBoxBinarize2:
            self.canvas_2.binary = state == Qt.CheckState.Checked  # Update binarization state
            foreground_metric = self.ComboBoxForeground2.currentText()
            background_metric = self.ComboBoxBackground2.currentText()
            canvas = self.canvas_2

        if self.current_image_idx is None or canvas is None:
            return  # No image selected or invalid canvas

        # Get the images based on selected dropdown values
        background_image = self.map_metric_to_image(background_metric, self.current_image_idx)
        foreground_image = self.map_metric_to_image(foreground_metric, self.current_image_idx)

        canvas.display_overlayed_image(background_image, foreground_image)  # Display the images


    def on_image_table_double_click(self, index):
        """ Handle double-click on table row and display the selected image. """
        source_index = self.proxy_model.mapToSource(index) # Convert sorted index to original
        row_idx = source_index.row()
        self.display_selected_image(row_idx)


    def display_selected_image(self, index):
        """ Display the image corresponding to batch_index and image_index, given selected combo box values. """
        image_data = self.images_df.iloc[index]

        if not image_data.empty:
            self.current_image_idx = index

            # get selected combo box values
            background_1 = self.ComboBoxBackground1.currentText()
            background_2 = self.ComboBoxBackground2.currentText()
            foreground_1 = self.ComboBoxForeground1.currentText()
            foreground_2 = self.ComboBoxForeground2.currentText()

            # get the images corresponding to the selected combo box values
            B1 = self.map_metric_to_image(background_1, self.current_image_idx)
            B2 = self.map_metric_to_image(background_2, self.current_image_idx)
            F1 = self.map_metric_to_image(foreground_1, self.current_image_idx)
            F2 = self.map_metric_to_image(foreground_2, self.current_image_idx)

            # display the images
            self.canvas_1.display_overlayed_image(B1, F1)
            self.canvas_2.display_overlayed_image(B2, F2)

            self.set_image_labels(image_data['batch_index'], image_data['image_index'])

            self.update_statistics()

            # Reset sliders
            self.ThresholdSlider_1.setValue(0)
            self.ThresholdSlider_2.setValue(0)




    def update_stats_table(self):
        """ Update the QTableView to match the order of images_df while showing stats_dataframe info. """
        if self.images_df.empty:
            return 

        # Create a view of stats_dataframe that only includes loaded images, keeping images_df order
        filtered_stats = self.images_df[["batch_index", "image_index"]].merge(
            self.stats_dataframe, on=["batch_index", "image_index"], how="left"
        )

        # Update the model with the new view
        self.stats_model.update_data(filtered_stats)
        self.proxy_model.invalidateFilter()  # Refresh filtering


    def set_interactive_elements_enabled(self, enabled: bool):
        """Enable or disable all interactive elements."""
        self.pushButton_2.setEnabled(enabled)
        self.nextButton.setEnabled(enabled)
        self.prevButton.setEnabled(enabled)
        self.ThresholdSlider_1.setEnabled(enabled)
        self.ComboBoxBackground1.setEnabled(enabled)
        self.ComboBoxBackground2.setEnabled(enabled)
        self.ComboBoxForeground1.setEnabled(enabled)
        self.ComboBoxForeground2.setEnabled(enabled)

    def start_dataframe_loading(self):
        """ Periodically check if dataframe is ready """

        # Show a message box and start checking for the dataframe
        self.loading_msgbox = QMessageBox(self)
        self.loading_msgbox.setWindowTitle("Loading")
        self.loading_msgbox.setText("Please wait, Dataframe is loading...")
        self.loading_msgbox.setIcon(QMessageBox.Icon.Information)
        self.loading_msgbox.setStandardButtons(QMessageBox.StandardButton.NoButton)  # No close button
        self.loading_msgbox.setModal(True)  # Make it modal to block interaction
        self.loading_msgbox.show()
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.loading_msgbox.width()) // 2
        y = (screen_geometry.height() - self.loading_msgbox.height()) // 2
        self.loading_msgbox.move(x, y)

        self.loading_msgbox.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_dataframe)
        self.timer.start(1500)  # Check every 1.5 seconds
        


    def check_dataframe(self):
        """ Fetch dataframe if available and stop timer once received """
        df = self.conn.get_dataframe()
        if df is not None:
            self.stats_dataframe = pd.read_json(df, dtype=True)
            # Add column called "IsLoaded" to dataframe to track if image is loaded
            self.stats_dataframe["IsLoaded"] = False
            self.timer.stop()  # Stop checking

            # Close the loading message box
            self.loading_msgbox.accept()

            # Enable interactive elements
            self.set_interactive_elements_enabled(True)
            
            # Populate the comboboxes
            self.populate_comboboxes()

            self.show_dataframe_popup(self.stats_dataframe)


    def show_dataframe_popup(self, df):
        """ Open the popup window to display the dataframe """
        self.dialog = DataFrameDialog(df, self)
        self.dialog.row_selected.connect(self.dataframe_selection_double_click)  # Connect signal
        self.dialog.load_batch_signal.connect(self.load_images_from_server) # Connect signal
        self.dialog.load_selected_images_signal.connect(self.load_images_from_server)  # Connect signal
        self.dialog.show()  # Show as modal popup

    def populate_comboboxes(self):
        """Populate the comboboxes with the columns of the dataframe_images"""
        # Setup the ComboBoxes for fore-/background selection
        foreground_options = ['Entropy','Counter-probability','Error Mask','Ground Truth','Prediction']
        background_options = ['Raw image','Entropy','Counter-probability','Error Mask','Ground Truth','Prediction']
        
        self.ComboBoxBackground1.addItems(background_options)
        self.ComboBoxBackground2.addItems(background_options)
        self.ComboBoxForeground1.addItems(foreground_options)
        self.ComboBoxForeground2.addItems(foreground_options)

    def map_metric_to_image(self, metric:str, row:int) -> np.ndarray:
        """Maps the column name to the corresponding image in the dataframe_images"""
        # Dictionary to map column names to their corresponding image
        metric_mapping = {'Entropy': 'entropy_image', 'Error Mask': 'Error Mask', 'Raw image': 'input_image',
                          'Perplexity': 'perplexity_image', 'Counter-probability': 'assuredness_image',
                          'Ground Truth': 'target_image', 'Prediction': 'prediction_image'}
        return self.images_df[metric_mapping[metric]][row]
    

    def dropdown_change(self, column:str, canvas:str):
        """Changes the image in [layer] on [canvas] to the one in the column specified by the new value of the dropdown""
        Assumes Column Error mask already exists in the dataframe"""

        if self.current_image_idx == None: return
        row = self.current_image_idx

        # Dictionary to map column names to their corresponding overlayed image
        metric_mapping = {'Entropy': 'entropy_image', 'Error Mask': 'Error Mask', 'Raw image': 'input_image',
                          'Perplexity': 'perplexity_image', 'Counter-probability': 'assuredness_image',
                          'Ground Truth': 'target_image', 'Prediction': 'prediction_image'}

        match canvas:
            case 1:
                background_column = metric_mapping[self.ComboBoxBackground1.currentText()]
                foreground_column = metric_mapping[self.ComboBoxForeground1.currentText()]
                B = self.images_df[background_column][row]
                F = self.images_df[foreground_column][row]
                self.canvas_1.display_overlayed_image(B,F)
                if F.dtype == np.bool: #if foreground is only binary, disable binarize box and threshold slider
                    self.checkBoxBinarize1.setEnabled(False)
                    self.ThresholdSlider_1.setEnabled(False)
                else: 
                    self.checkBoxBinarize1.setEnabled(True)
                    self.ThresholdSlider_1.setEnabled(True)
            case 2:
                background_column = metric_mapping[self.ComboBoxBackground2.currentText()]
                foreground_column = metric_mapping[self.ComboBoxForeground2.currentText()]
                B = self.images_df[background_column][row]
                F = self.images_df[foreground_column][row]
                self.canvas_2.display_overlayed_image(B,F)
                if F.dtype == np.bool: #if foreground is only binary, disable binarize box and threshold slider
                    self.checkBoxBinarize2.setEnabled(False)
                    self.ThresholdSlider_2.setEnabled(False)
                else: 
                    self.checkBoxBinarize2.setEnabled(True)
                    self.ThresholdSlider_2.setEnabled(True)

    
    def compute_errorMask(self, images_df ,row=None) ->np.ndarray:
        """Computes the Error Mask for an image and returns the computed mask.
        Parameters:
            images_df: The dataframe containing the images
            row (optional): The index of the image for which the error mask will be computed. Defaults to the index of the current Image if no value or None is passed
        Returns:
            mask: the computed mask"""
        
        if row == None: row = self.current_image_idx
        
        mask = (images_df['prediction_image'][row] != images_df['target_image'][row]).astype(np.bool)

        return mask


    def set_image_labels(self, batch_index=None, img_index=None):
        """ Set the labels for the current image """
        self.batchLabel.setText(f"Batch {batch_index}")
        self.imageLabel.setText(f"Image {img_index}")


    def clear_button_click(self):
        self.canvas_1.ax.clear()
        self.canvas_1.ax.axis('off')
        self.canvas_1.draw()

        self.canvas_2.ax.clear()
        self.canvas_2.ax.axis('off')
        self.canvas_2.draw()

        self.set_image_labels()


    def load_images_from_server(self, indices: list[tuple[int, int]]) -> pd.DataFrame:
        """ Get images from the server given a list of indices [(batch_index,image_index)]. """

        # Get only the images that are not already loaded
        indices = [(batch_index, img_index) for batch_index, img_index in indices
                   if not self.stats_dataframe[(self.stats_dataframe["batch_index"] == batch_index)
                                                & (self.stats_dataframe["image_index"] == img_index)]["IsLoaded"].values[0]]
        
        if not indices:
            return pd.DataFrame()
        
        images_df = pd.read_json(self.conn.get_images(indices))

        # Convert the images to numpy arrays
        for col in images_df.columns:
            if col.endswith("_image"):
                images_df[col] = images_df[col].apply(lambda x: np.array(x))

        # Set IsLoaded to True for the loaded images
        self.stats_dataframe.loc[self.stats_dataframe["batch_index"].isin(images_df["batch_index"])
                                 & self.stats_dataframe["image_index"].isin(images_df["image_index"]), "IsLoaded"] = True
                
    
        images_df["Error Mask"] = None
        # Compute the error mask for the loaded images
        for row in images_df.index:
            images_df['Error Mask'][row] = self.compute_errorMask(images_df, row)

        self.images_df = pd.concat([self.images_df,images_df], ignore_index=True)

        self.update_stats_table()  # Refresh the table

    

    def dataframe_selection_double_click(self, selected_row):
        """ Load selected image from server to local dataframe """

        indices = [(int(selected_row[0]), int(selected_row[1]))]
        # Get images from server
        self.load_images_from_server(indices)

    
    def get_sorted_index_from_images_df(self, original_index):
        """ Get the current index of an image in the sorted QTableView. """
        for sorted_row in range(self.proxy_model.rowCount()):
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(sorted_row, 0))
            if source_index.row() == original_index:
                return sorted_row  # Return the index in the sorted view
        return None  # If not found

    def get_original_index_from_sorted_table(self, sorted_index):
        """ Get the original images_df index from the sorted QTableView. """
        source_index = self.proxy_model.mapToSource(self.proxy_model.index(sorted_index, 0))
        return source_index.row()  # Return the original row index



    def next_image_click(self):
        """ Move to the next image based on the current sorted order. """
        if self.current_image_idx is None:
            return  

        # Get the current sorted index in the table
        sorted_index = self.get_sorted_index_from_images_df(self.current_image_idx)
        if sorted_index is None or sorted_index >= len(self.images_df) - 1:
            return  

        
        next_sorted_index = sorted_index + 1
        next_original_index = self.get_original_index_from_sorted_table(next_sorted_index)

        if next_original_index is not None:
            self.display_selected_image(next_original_index)

    def prev_image_click(self):
        """ Move to the previous image based on the current sorted order. """
        if self.current_image_idx is None:
            return  

        sorted_index = self.get_sorted_index_from_images_df(self.current_image_idx)
        if sorted_index is None or sorted_index <= 0:
            return  

        prev_sorted_index = sorted_index - 1
        prev_original_index = self.get_original_index_from_sorted_table(prev_sorted_index)

        if prev_original_index is not None:
            self.display_selected_image(prev_original_index)


    def slider_value_changed(self, value):
        """
        Handle the slider change event . 
        Args:
            value (int): The new value of the slider.
        """

        sender = self.sender()  # Get the slider that triggered the event
        canvas = None

        def map_value(value, in_min, in_max, out_min, out_max):
            """Linearly maps a value from one range to another."""
            return out_min + (float(value - in_min) / (in_max - in_min)) * (out_max - out_min)
                
        if sender == self.ThresholdSlider_1:
            background_metric = self.ComboBoxBackground1.currentText()
            foreground_metric = self.ComboBoxForeground1.currentText()
            canvas = self.canvas_1
        elif sender == self.ThresholdSlider_2:
            background_metric = self.ComboBoxBackground2.currentText()
            foreground_metric = self.ComboBoxForeground2.currentText()
            canvas = self.canvas_2

        background_image = self.map_metric_to_image(background_metric, self.current_image_idx)
        overlay_image = self.map_metric_to_image(foreground_metric, self.current_image_idx)

        # Map the slider value to the range of the entropy values
        min_value = overlay_image.min()
        max_value = overlay_image.max()
        threshold = map_value(value, 0, 100, min_value, max_value)

        # threshold the uncertainty image
        thresholded_image = self.threshold_image(overlay_image, threshold)

        # Display the thresholded image overlayed on the input image
        canvas.display_overlayed_image(background_image, thresholded_image)



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