import os
import cv2
import numpy as np
import threading
import queue
import time

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

import matplotlib.pyplot as plt

# -----------------------------
# CLASS
# -----------------------------
class NestSight:
    def __init__(self, developer_mode=False):
        self.developer_mode = developer_mode

        self.styles = getSampleStyleSheet()

        # Data storage
        self.top_points = []
        self.gap_values = []
        self.spike_regions = []
        self.processed_images = []

        self.fourier_result = "Not computed"
        self.spike_result = "Not computed"
        self.final_result = "UNDETERMINED"
        self.fft_score = 0

        self.frame_width = 60
        self.frame_x_start = 330

        # Queue system
        self.image_queue = queue.Queue(maxsize=200)
        self.running = True

        # Thread
        self.worker = threading.Thread(target=self.process_image_task, daemon=True)

        # Dev output
        self.temp_dir = "temp_report_images"
        self.output_pdf = "NestSight_report.pdf"

        self.submitted_count = 0
        self.process_count = 0

        if self.developer_mode:
            os.makedirs(self.temp_dir, exist_ok=True)

    # -----------------------------
    # START / STOP
    # -----------------------------
    def start(self):
        self.worker.start()

    def stop(self):
        self.running = False
        self.worker.join()

    # -----------------------------
    # ADD IMAGE (from camera)
    # -----------------------------
    def submit_image(self, img, index):
        self.image_queue.put((img, index))
        self.submitted_count += 1

    # -----------------------------
    # PROCESS TASK (THREAD)
    # -----------------------------
    def process_image_task(self):
        while self.running:
            try:
                img, idx = self.image_queue.get(timeout=0.1)
                self._process_single(img, idx)
            except queue.Empty:
                continue

        # -----------------------------
    # CHECK IF ALL IMAGES PROCESSED
    # -----------------------------
    def all_images_processed(self):
        """
        Returns True if the image queue is empty and all images submitted so far have been processed.
        """
        # Queue empty + top_points length matches number of submitted images
        # We assume each submit_image increments the queue, each processed image updates top_points/gap_values
        # Slightly more robust: check gap_values length against images submitted
        # return self.process_count == self.submitted_count
        return self.image_queue.empty()

    # -----------------------------
    # CORE IMAGE PROCESSING
    # -----------------------------
    def _process_single(self, img_full, image_index):
        img = img_full[120:315, 280:350].copy()
        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, laser_mask = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY)

        kernel = np.ones((1, 1), np.uint8)
        skeleton = cv2.morphologyEx(laser_mask, cv2.MORPH_OPEN, kernel)

        points = np.column_stack(np.where(skeleton > 0))

        if len(points) < 10:
            self.gap_values.append(0)
            return

        points_xy = points[:, [1, 0]].astype(np.float32)
        vx, vy, x0, y0 = [v[0] for v in cv2.fitLine(points_xy, cv2.DIST_L2, 0, 0.01, 0.01)]

        math_line_mask = np.zeros((h, w), dtype=np.uint8)
        p1 = (int(x0 - vx * 500), int(y0 - vy * 500))
        p2 = (int(x0 + vx * 500), int(y0 + vy * 500))
        cv2.line(math_line_mask, p1, p2, 255, 1)

        kernel = np.ones((1, 20), np.uint8)
        gate_mask = cv2.dilate(laser_mask, kernel)

        final = cv2.bitwise_and(math_line_mask, gate_mask)

        active = np.column_stack(np.where(final > 0))

        if len(active) == 0:
            self.gap_values.append(100)
            return

        y_min = np.min(active[:, 0])
        y_max = np.max(active[:, 0])

        self.top_points.append((image_index, int(y_min)))

        segment = np.zeros_like(math_line_mask)
        segment[y_min:y_max, :] = math_line_mask[y_min:y_max, :]

        total = np.count_nonzero(segment)
        present = np.count_nonzero(final)

        gap = (max(0, total - present) / total) * 100 if total > 0 else 0


        self.gap_values.append(gap)

        self.process_count += 1

        print(f"Processed frame : {image_index}")

        # Dev mode image saving
        if self.developer_mode:
            frame_data = {
            "overlay": img.copy(),      # final overlay image
            "laser_mask": laser_mask,
            "dilated_mask": gate_mask,
            "math_line": math_line_mask
            }

            self.processed_images.append(frame_data)

    # -----------------------------
    # ANALYSIS
    # -----------------------------
    def evaluate(self):
        self._compute_gap_stats()
        self._detect_spikes()
        self._analyze_fft()
        self._classify()

        return self.final_result

    def _compute_gap_stats(self):
        if not self.gap_values:
            self.avg_gap = self.max_gap = self.high_gap_ratio = 0
            return

        g = np.array(self.gap_values)
        self.avg_gap = np.mean(g)
        self.max_gap = np.max(g)
        self.high_gap_ratio = np.sum(g > 5) / len(g) * 100

    def _detect_spikes(self):
        if len(self.top_points) < 10:
            return

        y = np.array([p[1] for p in self.top_points])
        y_smooth = np.convolve(y, np.ones(7)/7, mode='same')

        baseline = np.median(y_smooth)
        deviation = y_smooth - baseline

        mask = deviation > 30

        self.spike_regions = []
        start = None

        for i, val in enumerate(mask):
            if val and start is None:
                start = i
            elif not val and start is not None:
                if i - start >= 5:
                    self.spike_regions.append((start, i))
                start = None

        # Handle any region that goes till the end
        if start is not None and len(mask) - start >= 5:
            self.spike_regions.append((start, len(mask)))

        # -----------------------------
        # Build human-readable result
        # -----------------------------
        if self.spike_regions:
            descriptions = []
            for start, end in self.spike_regions:
                width = end - start
                height = np.max(y[start:end]) - baseline
                descriptions.append(f"[{start}-{end}] width={width}, height={height:.1f}px")
            self.spike_result = "DEFECT: Missing feather section(s) at " + ", ".join(descriptions)
        else:
            self.spike_result = "No large localized defects detected"


    def _analyze_fft(self):
        if len(self.top_points) < 8:
            return

        y = np.array([p[1] for p in self.top_points])
        y = y - np.mean(y)

        fft_vals = np.fft.fft(y)
        mag = np.abs(fft_vals)[1:len(fft_vals)//2]

        score = np.max(mag) / (np.mean(mag) + 1e-6)

        self.fft_score = score

        # Classify result
        if score > 5:
            self.fourier_result = f"GOOD (strong periodic structure, score={score:.2f})"
        elif score > 1.8:
            self.fourier_result = f"BORDERLINE (minor irregularities, score={score:.2f})"
        else:
            self.fourier_result = f"DEFECT SUSPECTED (irregular structure, score={score:.2f})"

    def _classify(self):
        if self.max_gap > 25:
            self.final_result = "FAIL"
        elif self.avg_gap > 10:
            self.final_result = "FAIL"
        elif self.high_gap_ratio > 20:
            self.final_result = "FAIL"
        elif len(self.spike_regions) > 0:
            self.final_result = "FAIL"
        elif self.fft_score > 5:
            self.final_result = "PASS"
        else:
            self.final_result = "FAIL"

    # -----------------------------
    # DEV MODE RUN (DIRECTORY)
    # -----------------------------
    def run_developer_mode(self, input_dir):
        files = sorted([f for f in os.listdir(input_dir) if f.endswith((".png", ".jpg"))])

        for i, f in enumerate(files):
            img = cv2.imread(os.path.join(input_dir, f))
            self._process_single(img, i)

        result = self.evaluate()
        # self._generate_pdf()
        self.generate_pdf_report()
        self.reset()
        print("FINAL:", result)

    # -----------------------------
    # PDF (DEV ONLY)
    # -----------------------------
    def _generate_pdf(self):
        doc = SimpleDocTemplate(self.output_pdf)
        story = []

        story.append(Paragraph(f"Final Result: {self.final_result}", self.styles['Title']))
        story.append(Spacer(1, 20))

        for f in sorted(os.listdir(self.temp_dir)):
            if "overlay" in f:
                img = Image(os.path.join(self.temp_dir, f), width=4*inch, height=3*inch)
                story.append(img)
                story.append(Spacer(1, 10))

        doc.build(story)

    def generate_pdf_report(self):
        """
        Generates a detailed PDF report of the processed images, only in developer mode.
        Includes overlays, masks, math line, top-point graph, FFT spectrum, and defect analysis.
        """
        if not self.developer_mode:
            print("Developer mode disabled. PDF not generated.")
            return

        styles = getSampleStyleSheet()
        story = []

        # -----------------------------
        # Save images to temp dir if not already
        # -----------------------------
        os.makedirs(self.temp_dir, exist_ok=True)

        for idx, frame_data in enumerate(self.processed_images):
            # frame_data = {'overlay': overlay_img, 'laser_mask': mask, 'dilated_mask': dilated, 'math_line': line}
            files = {}
            for label, img in frame_data.items():
                path = os.path.join(self.temp_dir, f"img{idx}_{label}.png")
                cv2.imwrite(path, img)
                files[label] = path

            story.append(Paragraph(f"<b>Capture {idx}</b>", styles['Title']))
            story.append(Spacer(1, 10))
            if self.gap_values[idx] is not None:
                story.append(Paragraph(f"Gap Percentage: {self.gap_values[idx]:.2f}%", styles['Normal']))
            story.append(Spacer(1, 10))

            # Table of images (overlay, threshold, dilated, math line)
            row = [
                self.get_scaled_image(files["overlay"], 1.7 * inch),
                self.get_scaled_image(files["laser_mask"], 1.7 * inch),
                self.get_scaled_image(files["dilated_mask"], 1.7 * inch),
                self.get_scaled_image(files["math_line"], 1.7 * inch),
            ]

            table = Table([row], colWidths=[1.7*inch]*4)
            table.setStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),
                            ('VALIGN',(0,0),(-1,-1),'MIDDLE')])
            story.append(table)

            # Labels under images
            labels = [
                Paragraph("Overlay", styles['Normal']),
                Paragraph("Threshold", styles['Normal']),
                Paragraph("Dilated", styles['Normal']),
                Paragraph("Math Line", styles['Normal'])
            ]
            label_table = Table([labels], colWidths=[1.7*inch]*4)
            story.append(label_table)
            story.append(PageBreak())

        # -----------------------------
        # Add Top-point graph
        # -----------------------------
        if self.top_points:
            x = [p[0] for p in self.top_points]
            y = [p[1] for p in self.top_points]
            plt.figure()
            plt.plot(x, y, marker='o')
            for start, end in self.spike_regions:
                plt.axvspan(start, end, alpha=0.3, color='red')
            plt.xlabel("Image Index")
            plt.ylabel("Top Laser Point (pixels)")
            plt.title("Top Laser Edge Across Rotation")
            graph_path = os.path.join(self.temp_dir, "top_points_graph.png")
            plt.savefig(graph_path)
            plt.close()
            story.append(Paragraph("Top Laser Edge Across Rotation", styles['Title']))
            story.append(Spacer(1, 10))
            story.append(self.get_scaled_image(graph_path, 6*inch))
            story.append(PageBreak())

        # -----------------------------
        # FFT Graph
        # -----------------------------
        if len(self.top_points) >= 4:
            y_vals = np.array([p[1] for p in self.top_points])
            y_vals = y_vals - np.mean(y_vals)
            fft_vals = np.fft.fft(y_vals)
            freqs = np.fft.fftfreq(len(y_vals))
            mask = freqs > 0
            freqs = freqs[mask]
            magnitude = np.abs(fft_vals[mask])
            plt.figure()
            plt.stem(freqs, magnitude)
            plt.xlabel("Frequency (cycles per rotation)")
            plt.ylabel("Magnitude")
            plt.title("Fourier Spectrum of Laser Edge")
            fft_path = os.path.join(self.temp_dir, "fft_spectrum.png")
            plt.savefig(fft_path)
            plt.close()
            story.append(Paragraph("Fourier Frequency Analysis", styles['Title']))
            story.append(Spacer(1, 10))
            story.append(self.get_scaled_image(fft_path, 6*inch))
            story.append(PageBreak())

        # -----------------------------
        # Defect Analysis
        # -----------------------------
        story.append(Paragraph("<b>Spike Defect Detection:</b>", styles['Heading2']))
        story.append(Spacer(1, 5))
        story.append(Paragraph(self.spike_result, styles['Normal']))
        story.append(Spacer(1, 10))

        story.append(Paragraph("<b>FFT Defect Analysis Result:</b>", styles['Heading2']))
        story.append(Spacer(1, 5))
        story.append(Paragraph(self.fourier_result, styles['Normal']))
        story.append(Spacer(1, 10))

        # Gap statistics
        story.append(Paragraph("<b>Gap Statistics:</b>", styles['Heading2']))
        story.append(Paragraph(f"Average Gap: {self.avg_gap:.2f}%", styles['Normal']))
        story.append(Paragraph(f"Max Gap: {self.max_gap:.2f}%", styles['Normal']))
        story.append(Paragraph(f"Frames with Significant Gaps (>5%): {self.high_gap_ratio:.1f}%", styles['Normal']))
        story.append(Spacer(1, 10))

        story.append(Paragraph("<b>Final Result:</b>", styles['Heading2']))
        story.append(Paragraph(self.final_result, styles['Normal']))

        doc = SimpleDocTemplate(self.output_pdf)
        doc.build(story)
        print(f"PDF report saved: {self.output_pdf}")

    # -----------------------------
    # IMAGE SCALING
    # -----------------------------
    def get_scaled_image(self, path, max_width):

        img = ImageReader(path)
        iw, ih = img.getSize()

        scale = max_width / iw
        width = max_width
        height = ih * scale

        return Image(path, width=width, height=height)

    # -----------------------------
    # RESET / CLEANUP
    # -----------------------------
    def reset(self):
        """
        Clears all stored data to prepare for a fresh evaluation.
        """
        self.top_points = []
        self.gap_values = []
        self.spike_regions = []
        self.processed_images = []
        
        self.fourier_result = "Not computed"
        self.spike_result = "Not computed"
        self.final_result = "UNDETERMINED"

        self.submitted_count = 0
        self.process_count = 0

        # Optionally clear temp images in developer mode
        if self.developer_mode:
            for f in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, f))

def main():
    profiler = NestSight(developer_mode=True)
    profiler.run_developer_mode("captures_2")

if __name__ == "__main__":
    start = time.perf_counter()
    main()
    end = time.perf_counter()

    print(f"Images processed in: {(end - start) * 1000:.2f} ms") 
