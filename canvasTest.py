import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class ImageCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = fig.add_subplot(111)
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
        self.setWindowTitle("NumPy Image Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout for the central widget
        layout = QVBoxLayout(central_widget)

        # Matplotlib Canvas
        self.canvas = ImageCanvas(self, width=5, height=4, dpi=100)
        layout.addWidget(self.canvas)

        # Example NumPy array representing an image
        image_array = self.generate_sample_image()
        self.canvas.display_image(image_array)

    def generate_sample_image(self):
        """Generate a sample grayscale image using NumPy."""
        x = np.linspace(0, 4 * np.pi, 400)
        y = np.linspace(0, 4 * np.pi, 400)
        x, y = np.meshgrid(x, y)
        z = np.sin(x) ** 2 + np.cos(y) ** 2
        return z

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
