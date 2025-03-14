#!/usr/bin/env python3
import sys
import os
import threading
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QFileDialog, QSpinBox, QTextEdit, 
                           QCheckBox, QLineEdit, QTabWidget, QGridLayout, QGroupBox,
                           QComboBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor, QTextCursor

# Import functions from analyzer modules
from dockerfile_parser import extract_base_images
from image_analyzer import analyze_image_tags
from utils import load_custom_rules

class OutputRedirector:
    """Class to redirect stdout to a text widget"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        if '\n' in self.buffer:
            lines = self.buffer.split('\n')
            self.buffer = lines[-1]
            for line in lines[:-1]:
                self.text_widget.append(line)
        self.text_widget.moveCursor(QTextCursor.End)

    def flush(self):
        if self.buffer:
            self.text_widget.append(self.buffer)
            self.buffer = ""

class AnalysisThread(QThread):
    """Thread to run analysis in background"""
    finished = pyqtSignal(list)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, dockerfile_path, threshold, force_level, private_registries, custom_rules):
        super().__init__()
        self.dockerfile_path = dockerfile_path
        self.threshold = threshold
        self.force_level = force_level
        self.private_registries = private_registries
        self.custom_rules = custom_rules

    def run(self):
        try:
            self.progress.emit(f"Analyzing Dockerfile: {self.dockerfile_path}")
            
            # Extract images from Dockerfile
            image_info_list = extract_base_images(self.dockerfile_path)
            
            if not image_info_list:
                self.error.emit("No images found in Dockerfile.")
                return
                
            self.progress.emit(f"Found {len(image_info_list)} images in Dockerfile")
            
            results = []
            
            # Analyze each image
            for i, info in enumerate(image_info_list, 1):
                self.progress.emit(f"Analyzing image {i} of {len(image_info_list)}: {info['image']}")
                result = analyze_image_tags(
                    info['image'], 
                    i, 
                    len(image_info_list), 
                    self.threshold,
                    self.force_level,
                    self.private_registries,
                    self.custom_rules
                )
                results.append(result)
                
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"Error during analysis: {str(e)}")


class DockerVersionAnalyzerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Docker Image Version Analyzer')
        self.setGeometry(100, 100, 1000, 800)
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Top panel with settings
        settings_group = QGroupBox("Analysis Settings")
        settings_layout = QGridLayout()
        settings_group.setLayout(settings_layout)
        
        # Dockerfile selection
        self.dockerfile_path_edit = QLineEdit()
        self.dockerfile_path_edit.setPlaceholderText("Path to Dockerfile")
        self.dockerfile_path_edit.setReadOnly(True)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_dockerfile)
        
        settings_layout.addWidget(QLabel("Dockerfile:"), 0, 0)
        settings_layout.addWidget(self.dockerfile_path_edit, 0, 1)
        settings_layout.addWidget(self.browse_button, 0, 2)
        
        # Version threshold
        self.threshold_spinner = QSpinBox()
        self.threshold_spinner.setRange(1, 10)
        self.threshold_spinner.setValue(3)  # Default value
        self.threshold_spinner.setToolTip("Number of versions after which an image is marked as outdated")
        
        settings_layout.addWidget(QLabel("Version Threshold:"), 1, 0)
        settings_layout.addWidget(self.threshold_spinner, 1, 1)
        
        # Version level
        self.level_combo = QComboBox()
        self.level_combo.addItem("Automatic Detection", None)
        self.level_combo.addItem("Major Version", 1)
        self.level_combo.addItem("Minor Version", 2)
        self.level_combo.addItem("Patch Version", 3)
        
        settings_layout.addWidget(QLabel("Version Level:"), 2, 0)
        settings_layout.addWidget(self.level_combo, 2, 1)
        
        # Private registries
        self.registry_edit = QLineEdit()
        self.registry_edit.setPlaceholderText("Enter private registries separated by commas")
        
        settings_layout.addWidget(QLabel("Private Registries:"), 3, 0)
        settings_layout.addWidget(self.registry_edit, 3, 1)
        
        # Rules file
        self.rules_path_edit = QLineEdit()
        self.rules_path_edit.setPlaceholderText("Path to JSON rules file (optional)")
        self.rules_path_edit.setReadOnly(True)
        
        self.rules_button = QPushButton("Browse...")
        self.rules_button.clicked.connect(self.browse_rules)
        
        settings_layout.addWidget(QLabel("Rules File:"), 4, 0)
        settings_layout.addWidget(self.rules_path_edit, 4, 1)
        settings_layout.addWidget(self.rules_button, 4, 2)
        
        # Analyze button
        self.analyze_button = QPushButton("Analyze")
        self.analyze_button.clicked.connect(self.start_analysis)
        self.analyze_button.setEnabled(False)  # Initially disabled
        
        settings_layout.addWidget(self.analyze_button, 5, 0, 1, 3)
        
        main_layout.addWidget(settings_group)
        
        # Tabs for results and logs
        self.tabs = QTabWidget()
        
        # Log tab
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.tabs.addTab(self.log_widget, "Logs")
        
        # Results tab with table
        self.results_table = QTableWidget()
        self.setup_results_table()
        self.tabs.addTab(self.results_table, "Results")
        
        main_layout.addWidget(self.tabs)
        
        # Redirect output to log widget
        self.stdout_redirector = OutputRedirector(self.log_widget)
        
        # Status bar
        self.statusBar().showMessage('Ready')
        
        # Signal connections
        self.dockerfile_path_edit.textChanged.connect(self.validate_inputs)
        
    def setup_results_table(self):
        """Setup the results table"""
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Image", "Status", "Current Version", "Recommended Version", "Message"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
        
    def browse_dockerfile(self):
        """Open file dialog to select Dockerfile"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Dockerfile", "", 
            "Dockerfile (Dockerfile*);; All Files (*)", options=options
        )
        if file_path:
            self.dockerfile_path_edit.setText(file_path)
            
    def browse_rules(self):
        """Open file dialog to select rules file"""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Rules File", "", 
            "JSON Files (*.json);; All Files (*)", options=options
        )
        if file_path:
            self.rules_path_edit.setText(file_path)
            
    def validate_inputs(self):
        """Check if all required fields are filled"""
        if self.dockerfile_path_edit.text():
            self.analyze_button.setEnabled(True)
        else:
            self.analyze_button.setEnabled(False)
            
    def start_analysis(self):
        """Start analysis in a separate thread"""
        # Clear previous results
        self.log_widget.clear()
        self.results_table.setRowCount(0)
        
        # Get values from controls
        dockerfile_path = self.dockerfile_path_edit.text()
        threshold = self.threshold_spinner.value()
        
        level_index = self.level_combo.currentIndex()
        force_level = self.level_combo.itemData(level_index)
        
        private_registries = [r.strip() for r in self.registry_edit.text().split(',') if r.strip()]
        
        custom_rules = {}
        if self.rules_path_edit.text():
            try:
                custom_rules = load_custom_rules(self.rules_path_edit.text())
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Cannot load rules file: {str(e)}")
                return
        
        # Switch to logs tab
        self.tabs.setCurrentIndex(0)
        
        # Redirect standard output
        self.old_stdout = sys.stdout
        sys.stdout = self.stdout_redirector
        
        # Create and start analysis thread
        self.analysis_thread = AnalysisThread(
            dockerfile_path, threshold, force_level, private_registries, custom_rules
        )
        self.analysis_thread.progress.connect(self.update_progress)
        self.analysis_thread.error.connect(self.show_error)
        self.analysis_thread.finished.connect(self.analysis_finished)
        
        # Disable analyze button during processing
        self.analyze_button.setEnabled(False)
        self.statusBar().showMessage('Analyzing...')
        
        # Start analysis
        self.analysis_thread.start()
        
    def update_progress(self, message):
        """Update status bar with analysis progress"""
        self.statusBar().showMessage(message)
        
    def show_error(self, error_message):
        """Display error message"""
        QMessageBox.critical(self, "Error", error_message)
        self.analyze_button.setEnabled(True)
        self.statusBar().showMessage('Ready')
        
        # Restore standard output
        sys.stdout = self.old_stdout
        
    def analysis_finished(self, results):
        """Handle analysis completion and display results"""
        # Restore standard output
        sys.stdout = self.old_stdout
        
        # Update results table
        self.update_results_table(results)
        
        # Switch to results tab
        self.tabs.setCurrentIndex(1)
        
        # Update UI
        self.analyze_button.setEnabled(True)
        self.statusBar().showMessage('Analysis completed')
        
    def update_results_table(self, results):
        """Update results table"""
        self.results_table.setRowCount(len(results))
        
        for i, result in enumerate(results):
            # Image
            self.results_table.setItem(i, 0, QTableWidgetItem(result['image']))
            
            # Status
            status_item = QTableWidgetItem(result['status'])
            if result['status'] == 'UP-TO-DATE':
                status_item.setBackground(QColor(200, 255, 200))  # Green
            elif result['status'] == 'OUTDATED':
                status_item.setBackground(QColor(255, 200, 200))  # Red
            elif result['status'] == 'WARNING':
                status_item.setBackground(QColor(255, 255, 200))  # Yellow
            else:
                status_item.setBackground(QColor(220, 220, 220))  # Gray
            self.results_table.setItem(i, 1, status_item)
            
            current_tag = result.get('current', 'N/A')
            self.results_table.setItem(i, 2, QTableWidgetItem(current_tag))
            
            recommended = result.get('recommended', 'N/A')
            self.results_table.setItem(i, 3, QTableWidgetItem(recommended))
            
            self.results_table.setItem(i, 4, QTableWidgetItem(result['message']))
        
        self.results_table.resizeColumnsToContents()

def main():
    app = QApplication(sys.argv)
    ex = DockerVersionAnalyzerGUI()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()