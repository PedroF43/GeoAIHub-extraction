import fitz
from collections import defaultdict
from typing import List, Tuple, Optional
import re


def extract_table_data(
    page: fitz.Page, pattern: re.Pattern
) -> Optional[Tuple[List, List]]:
    """
    Extract table lines and headers from a page.

    Args:
    page (fitz.Page): The page to extract data from.
    pattern (re.Pattern): Regex pattern to match table headers.

    Returns:
    Optional[Tuple[List, List]]: Line coordinates and table coordinates if found, None otherwise.
    """
    if "Table" not in page.get_text("text"):
        return None

    table_coordinates = []
    line_coordinates = []
    # Extract table headers
    horizontal_count = 0
    vertical_count = 0
    for block in page.get_text("dict")["blocks"]:
        if block["type"] == 0:  # Text block
            for line in block["lines"]:
                dir_angle = line.get(
                    "dir", (1, 0)
                )  # Default to (1, 0) if "dir" key not present
                for span in line["spans"]:
                    if dir_angle == (1, 0):  # Horizontal
                        horizontal_count += 1
                    elif dir_angle == (0, -1):  # Vertical
                        vertical_count += 1

                    if pattern.fullmatch(span["text"]):
                        table_coordinates.append(
                            [span["text"], span["bbox"][1], page.number]
                        )

    # Extract lines and rectangles
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] in ("re", "l"):
                bbox = fitz.Rect(item[1:5]) if item[0] == "l" else fitz.Rect(item[1])
                bbox += (-1, -1, 1, 1)  # Adjust for precision
                if 50 < bbox[1] < 720 and abs(bbox[1] - bbox[3]) < 10:
                    line_coordinates.append([bbox, page.number])

    if horizontal_count < vertical_count:
        line_coordinates = "vertical"

    return (
        (line_coordinates, table_coordinates)
        if line_coordinates and table_coordinates
        else None
    )


def group_table_elements(line_coordinates: List, table_coordinates: List) -> List:
    """
    Group table elements by page and create bounding boxes.
    Also merges lines that are on the same horizontal plane but broken up.

    Args:
    line_coordinates (List): List of line coordinates.
    table_coordinates (List): List of table coordinates.

    Returns:
    List: List of bounding boxes for tables.
    """
    tables_by_page = defaultdict(list)
    lines_by_page = defaultdict(list)

    for table in table_coordinates:
        tables_by_page[table[-1]].append(table)

    for line in line_coordinates:
        lines_by_page[line[1]].append(line[0])

    # Merge lines that are on the same horizontal plane
    for page in lines_by_page:
        lines = lines_by_page[page]  # List of coordinates
        # Assuming each coordinate is [x1, y1, x2, y2]
        # Merge lines on the same horizontal plane
        # First, sort lines by y1
        lines_sorted = sorted(lines, key=lambda l: l[1])  # l[1] is y1
        tolerance = 2  # Adjust as needed based on coordinate precision
        merged_lines = []
        i = 0
        n = len(lines_sorted)
        while i < n:
            line = lines_sorted[i]
            y = line[1]  # y1
            current_group = [line]
            current_y = y
            j = i + 1
            while j < n:
                next_line = lines_sorted[j]
                next_y = next_line[1]
                if abs(next_y - current_y) <= tolerance:
                    current_group.append(next_line)
                    j += 1
                else:
                    break
            # Merge current_group
            x1s = [l[0] for l in current_group]
            x2s = [l[2] for l in current_group]
            min_x1 = min(x1s)
            max_x2 = max(x2s)
            # Assuming y1 and y2 are the same for all lines in current_group
            merged_line = [min_x1, current_y, max_x2, current_y]
            merged_lines.append(merged_line)
            i = j
        # Replace lines_by_page[page] with merged_lines
        lines_by_page[page] = merged_lines

    bounding_boxes = []

    for page, tables in tables_by_page.items():
        sorted_tables = sorted(tables, key=lambda t: t[1])

        for i, table in enumerate(sorted_tables):
            next_y = (
                sorted_tables[i + 1][1] if i + 1 < len(sorted_tables) else float("inf")
            )

            # Adjusted to account for merged lines
            bbox = [line for line in lines_by_page[page] if table[1] < line[1] < next_y]

            if bbox:
                bounding_boxes.append([bbox, page])

    return bounding_boxes


def create_table_bounding_boxes(rectangles: List) -> List:
    """
    Create complete bounding boxes for tables.

    Args:
    rectangles (List): List of rectangles representing table elements.

    Returns:
    List: List of complete table bounding boxes.
    """
    if not rectangles:
        return []

    final_tables = []

    for page_rectangles, page_num in rectangles:
        sorted_rectangles = sorted(page_rectangles, key=lambda rect: (rect[1], rect[0]))
        grouped_rectangles = []
        current_group = [sorted_rectangles[0]]

        for rect in sorted_rectangles[1:]:
            if abs(rect[1] - current_group[-1][1]) <= 3:
                current_group.append(rect)
            else:
                grouped_rectangles.append(current_group)
                current_group = [rect]

        if current_group:
            grouped_rectangles.append(current_group)

        if grouped_rectangles:
            x0 = grouped_rectangles[0][0][0]
            x1 = grouped_rectangles[0][0][2]
            y0 = grouped_rectangles[0][0][1]
            y1 = grouped_rectangles[-1][0][1]

            final_tables.append([x0, y0, x1, y1, page_num])

    return final_tables


def extract_tables(page: fitz.Page, pattern: re.Pattern) -> Optional[List]:
    """
    Extract tables from a page.

    Args:
    page (fitz.Page): The page to extract tables from.
    pattern (re.Pattern): Regex pattern to match table headers.

    Returns:
    Optional[List]: List of table bounding boxes if found, None otherwise.
    """
    table_data = extract_table_data(page, pattern)

    if table_data == "Vertical Page":
        return table_data

    if table_data:
        line_coordinates, table_coordinates = table_data
        if line_coordinates == "vertical":
            return [[0, 0, page.rect.width, page.rect.height], page.number]
        else:
            grouped_elements = group_table_elements(line_coordinates, table_coordinates)
        return create_table_bounding_boxes(grouped_elements)
    return None


def patterns(requested_pattern):
    if requested_pattern == "table_pattern":
        table_pattern = re.compile(r"^Table \d[:]?\s*$|^Table \d[:]?\s*")
        return table_pattern
