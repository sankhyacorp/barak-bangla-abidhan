# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
import cv2
import numpy as np
import os

def split_image_56():
    img_path = r'c:\Users\sankhyac\Downloads\Dict\Images\Barak Upatyakar Ancholik Bhashar Abhidhan O Bhashatatwa - Copy\IMG_0056.jpg'
    
    if not os.path.exists(img_path):
        print(f"Image not found at {img_path}")
        return

    print(f"Loading {img_path}...")
    img = cv2.imread(img_path)
    h, w = img.shape[:2]

    # Convert to grayscale for analysis
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Focus on the center region (40% to 60% of width) where the line should be
    center_start = int(w * 0.4)
    center_end = int(w * 0.6)
    center_region = gray[:, center_start:center_end]

    # Threshold to find black pixels (the vertical line)
    _, thresh = cv2.threshold(center_region, 100, 255, cv2.THRESH_BINARY_INV)

    # Find lines using Hough Transform
    print("Analyzing image to find the vertical black line...")
    lines = cv2.HoughLinesP(thresh, 1, np.pi/180, threshold=100, minLineLength=200, maxLineGap=50)

    best_line = None
    max_len = 0

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Filter for vertical lines (allow slight slant)
            if abs(x1 - x2) < 50:
                length = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)
                if length > max_len:
                    max_len = length
                    best_line = (x1 + center_start, y1, x2 + center_start, y2)

    if best_line:
        print(f"Found the most prominent vertical line at x={best_line[0]} (length: {int(max_len)}px)")
        
        # Calculate the average x coordinate of the line
        line_x = (best_line[0] + best_line[2]) // 2
        
        # Split the image, adding padding to discard the black line itself
        padding = 15
        left_crop = img[:, :line_x - padding]
        right_crop = img[:, line_x + padding:]
        
        out_dir = r'c:\Users\sankhyac\Downloads\Dict\SplitImages'
        os.makedirs(out_dir, exist_ok=True)
        
        left_out = os.path.join(out_dir, 'IMG_0056_left.jpg')
        right_out = os.path.join(out_dir, 'IMG_0056_right.jpg')
        
        cv2.imwrite(left_out, left_crop)
        cv2.imwrite(right_out, right_crop)
        
        print(f"Successfully split the image!")
        print(f"Left column saved to: {left_out}")
        print(f"Right column saved to: {right_out}")
    else:
        print("Could not find a clear vertical line.")

if __name__ == "__main__":
    split_image_56()
