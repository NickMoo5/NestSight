import os
import cv2
import numpy as np
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

import time

# -----------------------------
# SETTINGS
# -----------------------------
INPUT_DIR = "captures"
OUTPUT_PDF = "laser_report.pdf"
TEMP_DIR = "temp_report_images"

os.makedirs(TEMP_DIR, exist_ok=True)

styles = getSampleStyleSheet()

# store topmost points for graph
top_points = []
defect_result = "Not Computed"

spike_result = "Not computed"
spike_regions = []

gap_values = []

# -----------------------------
# IMAGE SCALING
# -----------------------------
def get_scaled_image(path, max_width):

    img = ImageReader(path)
    iw, ih = img.getSize()

    scale = max_width / iw
    width = max_width
    height = ih * scale

    return Image(path, width=width, height=height)


# -----------------------------
# PROCESS IMAGE
# -----------------------------
def process_image(image_path, name_prefix, image_index):
    img_full = cv2.imread(image_path)
    if img_full is None:
        return None

    # 1. Crop the image first
    img = img_full[100:320, 330:390].copy()
    h, w = img.shape[:2]

    # 2. Convert to Grayscale (Brightness) instead of HSV
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Create a Threshold Mask
    # We use 200 to catch only the brightest parts of the laser
    _, laser_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # Clean up the mask (remove tiny speckles)
    kernel = np.ones((3, 3), np.uint8)
    skeleton = cv2.morphologyEx(laser_mask, cv2.MORPH_OPEN, kernel)

    # 4. Find Points and Fit Line
    points = np.column_stack(np.where(skeleton > 0))
    
    math_line_mask = np.zeros((h, w), dtype=np.uint8)
    final_gapped_line = np.zeros((h, w), dtype=np.uint8)
    output = img.copy()
    gap_percentage = None
    
    if len(points) > 10:
        # Prepare points for line fitting
        points_xy = points[:, [1, 0]].astype(np.float32)

        # Fit the mathematical center line
        line_params = cv2.fitLine(points_xy, cv2.DIST_L2, 0, 0.01, 0.01)
        vx, vy, x0, y0 = [v[0] for v in line_params]

        # Draw the math line across the whole crop
        p1 = (int(x0 - vx * 500), int(y0 - vy * 500))
        p2 = (int(x0 + vx * 500), int(y0 + vy * 500))
        cv2.line(math_line_mask, p1, p2, 255, 1)

        kernel = np.ones((2, 15), np.uint8)   # height=1, width=8        only grow horizontally
        gate_mask = cv2.dilate(laser_mask, kernel)
        final_gapped_line = cv2.bitwise_and(math_line_mask, gate_mask)

        # 5. Extract Topmost Point & Gaps
        active_points = np.column_stack(np.where(final_gapped_line > 0))
        if len(active_points) > 0:
            y_min = np.min(active_points[:, 0])
            top_points.append((image_index, int(y_min)))

            y_max = np.max(active_points[:, 0])
            math_line_segment = np.zeros_like(math_line_mask)
            math_line_segment[y_min:y_max, :] = math_line_mask[y_min:y_max, :]

            total_possible = np.count_nonzero(math_line_segment)
            actual_present = np.count_nonzero(final_gapped_line)

            if total_possible > 0:
                gap_percentage = (max(0, total_possible - actual_present) / total_possible) * 100
                cv2.putText(output, f"Gaps: {gap_percentage:.1f}%", (5, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
    
    # slicing horizontally
    # if len(points) > 10:
    #     # 1. Determine the vertical bounds of the laser
    #     y_coords = points[:, 0]
    #     y_min, y_max = np.min(y_coords), np.max(y_coords)
        
    #     top_points.append((image_index, int(y_min)))
        
    #     # 2. Collapse the mask horizontally (Projection)
    #     # This checks if ANY pixel in a row is part of the laser
    #     row_sum = np.sum(skeleton[y_min:y_max+1, :], axis=1)
        
    #     # 3. Calculate coverage
    #     # A row is 'filled' if the sum of pixels in that row > 0
    #     rows_with_laser = np.count_nonzero(row_sum)
    #     total_rows = y_max - y_min + 1
        
    #     if total_rows > 0:
    #         # We calculate "Presence" first, then convert to Gap
    #         presence_percentage = (rows_with_laser / total_rows) * 100
    #         gap_percentage = 100 - presence_percentage
            
    #         cv2.putText(output, f"Gaps: {gap_percentage:.1f}%", (5, 20),
    #                     cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    # Visual Overlay
    output[final_gapped_line > 0] = [0, 255, 0]

    # Save temp images for report
    files = {}
    def save_temp(label, data):
        p = os.path.join(TEMP_DIR, f"{name_prefix}_{label}.png")
        cv2.imwrite(p, data)
        files[label] = p

    save_temp("overlay", output)
    save_temp("thresh_mask", laser_mask)
    save_temp("dilated_mask", gate_mask)
    save_temp("math_line", math_line_mask)

    return files, gap_percentage


# -----------------------------
# CREATE GRAPH
# -----------------------------
def generate_top_point_graph():

    if len(top_points) == 0:
        return None

    x = [p[0] for p in top_points]
    y = [p[1] for p in top_points]

    plt.figure()

    plt.plot(x, y, marker='o')

    # for i, txt in enumerate(x):
    #     plt.annotate(str(txt), (x[i], y[i]))
    # Highlight detected spike regions
    for start, end in spike_regions:
        plt.axvspan(start, end, alpha=0.3)


    plt.xlabel("Image Index (Rotation Order)")
    plt.ylabel("Top-most Laser Point (pixels)")
    plt.title("Top Laser Edge Across Rotation")

    graph_path = os.path.join(TEMP_DIR, "top_points_graph.png")
    plt.savefig(graph_path)
    plt.close()

    return graph_path

def generate_fft_graph():

    if len(top_points) < 4:
        return None

    # Extract y values
    y = np.array([p[1] for p in top_points])

    # Remove DC offset (center the signal)
    y = y - np.mean(y)

    # FFT
    fft_vals = np.fft.fft(y)
    freqs = np.fft.fftfreq(len(y))

    # Only keep positive frequencies
    pos_mask = freqs > 0
    freqs = freqs[pos_mask]
    magnitude = np.abs(fft_vals[pos_mask])

    plt.figure()

    plt.stem(freqs, magnitude)

    plt.xlabel("Frequency (cycles per rotation)")
    plt.ylabel("Magnitude")
    plt.title("Fourier Spectrum of Laser Edge")

    graph_path = os.path.join(TEMP_DIR, "fft_spectrum.png")

    plt.savefig(graph_path)
    plt.close()

    return graph_path

def analyze_fft_defects():

    global defect_result

    if len(top_points) < 8:
        defect_result = "Not enough samples"
        return

    y = np.array([p[1] for p in top_points])

    # remove DC offset
    y = y - np.mean(y)

    fft_vals = np.fft.fft(y)
    magnitude = np.abs(fft_vals)

    # ignore DC component
    magnitude = magnitude[1:len(magnitude)//2]

    dominant = np.max(magnitude)
    avg_energy = np.mean(magnitude)

    # periodicity score
    score = dominant / (avg_energy + 1e-6)

    if score > 3:
        defect_result = f"GOOD (strong periodic structure, score={score:.2f})"
    elif score > 1.8:
        defect_result = f"BORDERLINE (score={score:.2f})"
    else:
        defect_result = f"DEFECT SUSPECTED (irregular spectrum, score={score:.2f})"

# -----------------------------
# SPIKE / DEFECT DETECTION
# -----------------------------
def smooth_signal(y, window=7):
    return np.convolve(y, np.ones(window)/window, mode='same')


def find_regions(mask, min_length=5):
    regions = []
    start = None

    for i, val in enumerate(mask):
        if val and start is None:
            start = i
        elif not val and start is not None:
            if i - start >= min_length:
                regions.append((start, i))
            start = None

    if start is not None and len(mask) - start >= min_length:
        regions.append((start, len(mask)))

    return regions


def detect_spike_defects():
    global spike_result, spike_regions

    if len(top_points) < 10:
        spike_result = "Not enough samples"
        spike_regions = []
        return

    y = np.array([p[1] for p in top_points])

    # Smooth signal
    y_smooth = smooth_signal(y)

    # Baseline (robust)
    baseline = np.median(y_smooth)

    # Deviation from baseline
    deviation = y_smooth - baseline

    # Threshold (tune this if needed)
    threshold = 30

    mask = deviation > threshold

    # Find consecutive regions
    spike_regions = find_regions(mask, min_length=5)

    if spike_regions:
        descriptions = []
        for start, end in spike_regions:
            width = end - start
            height = np.max(y[start:end]) - baseline
            descriptions.append(
                f"[{start}-{end}] width={width}, height={height:.1f}px"
            )

        spike_result = "DEFECT: Missing feather section(s) at " + ", ".join(descriptions)
    else:
        spike_result = "No large localized defects detected"

# -----------------------------
# GAP STATISTICS
# -----------------------------
def compute_gap_statistics():
    global avg_gap, max_gap, high_gap_ratio

    if len(gap_values) == 0:
        avg_gap = 0
        max_gap = 0
        high_gap_ratio = 0
        return

    g = np.array(gap_values)

    avg_gap = np.mean(g)
    max_gap = np.max(g)

    # % of frames with significant gaps
    high_gap_frames = np.sum(g > 5)  # threshold (tune)
    high_gap_ratio = (high_gap_frames / len(g)) * 100

def classify_final_result():
    global final_result

    final_result = "UNDETERMINED"

    # FFT score
    fft_score = 0
    if "score=" in defect_result:
        try:
            fft_score = float(defect_result.split("score=")[1].strip(")"))
        except:
            fft_score = 0

    has_spike_defect = len(spike_regions) > 0

    # -----------------------------
    # DECISION LOGIC
    # -----------------------------

    # 🔴 HARD FAIL conditions
    if max_gap > 25:
        final_result = f"FAIL ❌ (Severe local damage, max gap={max_gap:.1f}%)"
        return

    if avg_gap > 10:
        final_result = f"FAIL ❌ (High overall material loss, avg gap={avg_gap:.1f}%)"
        return

    # 🟠 Moderate defects
    if high_gap_ratio > 20:
        final_result = f"FAIL ❌ (Widespread defects: {high_gap_ratio:.1f}% frames affected)"
        return

    if has_spike_defect:
        final_result = "FAIL ⚠️ (Localized structural defect detected)"
        return

    # 🟢 Structure check
    if fft_score > 3:
        final_result = "PASS ✅ (Uniform structure, minimal gaps)"
    elif fft_score > 1.8:
        final_result = "BORDERLINE ⚠️ (Minor irregularities)"
    else:
        final_result = "FAIL ❌ (Irregular structure)"

# -----------------------------
# GENERATE REPORT
# -----------------------------
def generate_report():
    story = []
    image_files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".jpg", ".png", ".jpeg"))
    ])

    for idx, filename in enumerate(image_files):
        path = os.path.join(INPUT_DIR, filename)
        result = process_image(path, f"img{idx}", idx)

        if result is None:
            continue

        files, gap = result

        if gap is not None:
            gap_values.append(gap)
        else:
            gap_values.append(0)

        story.append(Paragraph(f"<b>Capture {idx}: {filename}</b>", styles['Title']))
        
        if gap is not None:
            story.append(Paragraph(f"Gap Percentage: {gap:.2f}%", styles['Normal']))
        
        story.append(Spacer(1, 10))

        # --- NEW 3-COLUMN LOGIC ---
        # We want: [Overlay] [Thresh Mask] [Math Line]
        row = [
            get_scaled_image(files["overlay"], 1.7 * inch),
            get_scaled_image(files["thresh_mask"], 1.7 * inch),
            get_scaled_image(files["dilated_mask"], 1.7 * inch),
            get_scaled_image(files["math_line"], 1.7 * inch),
        ]

        # Create table with 3 columns
        table = Table([row], colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.7*inch])
        
        # Add some padding/styling to the table
        table.setStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        story.append(table)
        
        # Labels for the images
        labels = [
            Paragraph("<para align=center>Overlay</para>", styles['Normal']),
            Paragraph("<para align=center>Threshold</para>", styles['Normal']),
            Paragraph("<para align=center>Ideal Line</para>", styles['Normal'])
        ]
        label_table = Table([labels], colWidths=[2.4*inch, 2.4*inch, 2.4*inch])
        story.append(label_table)

        story.append(PageBreak())

    analyze_fft_defects()
    detect_spike_defects()
    compute_gap_statistics()
    classify_final_result()
    # -----------------------------
    # Add Graph Page
    # -----------------------------
    graph_path = generate_top_point_graph()

    if graph_path:

        story.append(Paragraph("Top Laser Edge Across Rotation", styles['Title']))
        story.append(Spacer(1, 20))

        story.append(get_scaled_image(graph_path, 6*inch))

        story.append(Spacer(1, 20))
        story.append(Paragraph("<b>Spike Defect Detection:</b>", styles['Heading2']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(spike_result, styles['Normal']))

    # -----------------------------
    # Add FFT Spectrum Page
    # -----------------------------
    fft_path = generate_fft_graph()

    if fft_path:

        story.append(PageBreak())
        story.append(Paragraph("Fourier Frequency Analysis", styles['Title']))
        story.append(Spacer(1, 20))

        story.append(get_scaled_image(fft_path, 6*inch))

        story.append(Spacer(1, 20))
        story.append(Paragraph("<b>Defect Analysis Result:</b>", styles['Heading2']))
        story.append(Spacer(1, 10))
        story.append(Paragraph(defect_result, styles['Normal']))

    story.append(Paragraph("<b>Gap Analysis:</b>", styles['Heading2']))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"Average Gap: {avg_gap:.2f}%", styles['Normal']))
    story.append(Paragraph(f"Max Gap: {max_gap:.2f}%", styles['Normal']))
    story.append(Paragraph(f"Frames with Significant Gaps (>5%): {high_gap_ratio:.1f}%", styles['Normal']))

    story.append(Paragraph("<b>Overall Result:</b>", styles['Heading2']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(final_result, styles['Normal']))

    doc = SimpleDocTemplate(OUTPUT_PDF)
    doc.build(story)

    print("PDF report saved:", OUTPUT_PDF)
        
# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    start = time.perf_counter()
    generate_report()
    end = time.perf_counter()

    print(f"Images processed in: {(end - start) * 1000:.2f} ms") 

    # Add 'laser surface profiler', laser stripe center extraction
