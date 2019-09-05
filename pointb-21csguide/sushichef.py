#!/usr/bin/env python

import os
import requests

from copy import copy
from PyPDF2 import PdfFileReader, PdfFileWriter

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license
from ricecooker.utils.pdf import PDFParser


DOWNLOADS_PATH = "downloads/"
SPLIT_PATH = ''.join([DOWNLOADS_PATH, '/21CSGuide_English_split/'])

POINTB_URL = 'http://www.pointb.is/s/'
CSGUIDE_PDF_EN = '21CSGuide_English.pdf'
CSGUIDE_PDF_EN_CROPPED = '21CSGuide_English_cropped.pdf'
CSGUIDE_PDF_MY = '21CSGuide_Myanmar.pdf'
CSGUIDE_PDF_MY_CROPPED = '21CSGuide_Myanmar_cropped.pdf'
PDF_URL_EN = ''.join([POINTB_URL, CSGUIDE_PDF_EN])
PDF_URL_MY = ''.join([POINTB_URL, CSGUIDE_PDF_MY])
PDF_PATH_EN = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN)
PDF_PATH_EN_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN_CROPPED)
PDF_PATH_MY = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY)
PDF_PATH_MY_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY_CROPPED)
PDFS = (
    { 'pdf_url': PDF_URL_EN, 'pdf_path': PDF_PATH_EN },
    # { 'pdf_url': PDF_URL_MY, 'pdf_path': PDF_PATH_MY },
)


def split_chapters_en():
    """
    Splits the chapters for the English PDF.
    """
    print('Splitting chapters for', PDF_PATH_EN_CROPPED)

    page_ranges = [
        {'title': 'Front Matter', 'page_start': 0, 'page_end': 13},
        {'title': 'Section 1 - Setting a Vision for Your 21st Century Learning Classroom', 'page_start': 13, 'page_end': 21},
        {'title': 'Section 2 - 21st Century Mindsets and Practices', 'page_start': 21, 'page_end': 61, 
        'children': [
            {'title': 'Mindset #1: Mindfulness', 'page_start': 23, 'page_end': 31},
            {'title': 'Mindset #2: Curiousity', 'page_start': 31, 'page_end': 37},
            {'title': 'Mindset #3: Growth', 'page_start': 37, 'page_end': 41},
            {'title': 'Mindset #4: Empathy', 'page_start': 41, 'page_end': 47},
            {'title': 'Mindset #5: Appreciation', 'page_start': 47, 'page_end': 51},
            {'title': 'Mindset #6: Experimentation', 'page_start': 51, 'page_end': 57},
            {'title': 'Mindset #7: Systems Thinking', 'page_start': 57, 'page_end': 61},
        ]
        },
        {'title': 'Section 3 - 21st Century Skills', 'page_start': 61, 'page_end': 69},
        {'title': 'Section 4 - Self-Discovery', 'page_start': 69, 'page_end': 95},
        {'title': 'Section 5 - 21st Century Skills Building For Teachers', 'page_start': 95, 'page_end': 109},
        {'title': 'Section 6 - Integrating 21st Century Skills Into Your Classroom', 'page_start': 109, 'page_end': 135},
        {'title': 'Thanks To Our Teachers', 'page_start': 135, 'page_end': 137},
    ]

    with PDFParser(PDF_PATH_EN_CROPPED, directory=SPLIT_PATH) as pdfparser:
        chapters = pdfparser.split_subchapters(jsondata=page_ranges)
        # for chapter in chapters:
        #     print(chapter)

    print('DONE splitting chapters for English PDF.')
    return True


def download_pdfs():
    try:
        for pdf in PDFS:
            pdf_url = pdf['pdf_url']
            pdf_path = pdf['pdf_path']
            # Do not download if file already exists.
            if os.path.exists(pdf_path):
                print('PDF already exists, NOT downloading:', pdf_path)
            else:
                print('Downloading PDF', pdf_url, 'TO', pdf_path)
                response = requests.get(pdf_url)
                assert response.status_code == 200
                # save .pdf to the downloads folder
                with open(pdf_path, 'wb') as pdf_file:
                    pdf_file.write(response.content)
                print('... DONE downloading.')

            # crop from two-paged pdf into single-page pdf
            print('Cropping from two-page into single-page...', pdf_path)
            pdf_path_cropped = pdf_path.replace('.pdf', '_cropped.pdf')
            split_left_right_pages(pdf_path, pdf_path_cropped)

            print_pdf_info(pdf_path_cropped)

            print('... DONE cropping.')

        return True
    except Exception as exc:
        print("ERROR: ", exc)
        return False


def get_dimensions(pdfin1):
    """
    Get dimensions of second page in PDF file `pdfin1`.
    Returns tuple: (half_width, full_height)
    """
    page = pdfin1.getPage(2)
    double_page_width = page.mediaBox.getUpperRight_x()
    page_width = double_page_width / 2
    page_height = page.mediaBox.getUpperRight_y()
    return page_width, page_height


def split_left_right_pages(pdfin_path, pdfout_path):
    """
    Splits the left and right halves of a page into separate pages.
    We also remove the binders between those separated pages.
    """
    # REF: https://gist.github.com/mdoege/0676e37ee2470fc755ea98177a560b4b
    # RELATED-REF: https://github.com/mstamy2/PyPDF2/issues/100 

    pdfin1 = PdfFileReader(open(pdfin_path, "rb"))  # used for left pages
    pdfout = PdfFileWriter()

    num_pages = pdfin1.getNumPages()
    page_ranges = [pdfin1.getPage(i) for i in range(0, num_pages)]
    for nn,left_page in enumerate(page_ranges):
        # use copy for the right pages
        right_page = copy(left_page)
        # copy the existing page dimensions
        (page_width, page_height,) = left_page.mediaBox.upperRight

        is_first_page = (nn == 0)
        is_last_page = (nn + 1 >= num_pages)
        if is_first_page or is_last_page:
            # The first page has the binder to its left while the last page 
            # has the binder to its right.
            binder_width = 40
            if is_first_page:
                (page_width, page_height,) = right_page.mediaBox.upperLeft
                right_page.mediaBox.upperLeft = (page_width + binder_width, page_height,)
            if is_last_page:
                (page_width, page_height,) = right_page.mediaBox.upperRight
                right_page.mediaBox.upperRight = (page_width - binder_width, page_height,)
        else:
            # Divide the width by 2 for the other pages (except first and last).
            # We also remove the binders on the left-side of the right pages
            # and the right-side of the left pages.
            page_width = page_width / 2
            binder_width = 20
            right_page.mediaBox.upperLeft = (page_width + binder_width, page_height,)
            left_page.mediaBox.upperRight = (page_width - binder_width, page_height,)
            pdfout.addPage(left_page)
        pdfout.addPage(right_page)

    with open(pdfout_path, "wb") as out_f:
        pdfout.write(out_f)


def print_pdf_info(pdf_path):
    pdf = PdfFileReader(open(pdf_path, "rb"))
    page_width, page_height = get_dimensions(pdf)
    print('PDF INFO:', page_width, page_height)
    num_pages = pdf.getNumPages()
    for page_num in range(0, num_pages):
        page = pdf.getPage(page_num)
        this_width = page.mediaBox.getUpperRight_x()
        this_height = page.mediaBox.getUpperRight_y()
        print('==> page', page_num, 'this_width', this_width, 'this_height', this_height)


def local_construct():
    if not download_pdfs():
        print("Download of PDFS FAILED!")
        return False

    if not split_chapters_en():
        print("Split chapters for English PDF FAILED!")
        return False


    main_topic = TopicNode(title="English", source_id="<21cs_en_id>")

    frontmatter_file = "0-Front-Matter.pdf"

    # Introduction
    front_doc_node = DocumentNode(
        title="Introduction",
        description="Introduction",
        source_id=frontmatter_file,
        license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(SPLIT_PATH, frontmatter_file),
                language="en"
            )
        ])
    main_topic.add_child(front_doc_node)
    return False


class PointBChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "PointB 21CS Guide",
        "CHANNEL_SOURCE_DOMAIN": "pointb.is",  # where you got the content (change me!!)
        "CHANNEL_SOURCE_ID": "test-21csguide",  # channel's unique id (change me!!)
        "CHANNEL_LANGUAGE": "mul",  # le_utils language code
        "CHANNEL_THUMBNAIL": None,  # TODO:
        "CHANNEL_DESCRIPTION": "Guide To Becoming A 21St Century Teacher",  # (optional)
    }

    def construct_channel(self, **kwargs):

        if not download_pdfs():
            print("Download of PDFS FAILED!")
            return False

        if not split_chapters_en():
            print("Split chapters for English PDF FAILED!")
            return False

        channel = self.get_channel(**kwargs)

        main_topic = TopicNode(title="English", source_id="<21cs_en_id>")
        main_topic2 = TopicNode(title="Burmese", source_id="<21cs_my_id>")
        channel.add_child(main_topic)
        channel.add_child(main_topic2)

        frontmatter_file = "0-Front-Matter.pdf"
        section_1_file = "1-Section-1---Setting-a-Vision-for-Your-21st-Century-Learning-Classroom.pdf"
        section_2_file = "2-Section-2---21st-Century-Mindsets-and-Practices.pdf"
        section_2_0_file = "2-0-Mindset-1-Mindfulness.pdf"
        section_2_1_file = "2-1-Mindset-2-Curiousity.pdf"
        section_2_2_file = "2-2-Mindset-3-Growth.pdf"
        section_2_3_file = "2-3-Mindset-4-Empathy.pdf"
        section_2_4_file = "2-4-Mindset-5-Appreciation.pdf"
        section_2_5_file = "2-5-Mindset-6-Experimentation.pdf"
        section_2_6_file = "2-6-Mindset-7-Systems-Thinking.pdf"
        section_3_file = "3-Section-3---21st-Century-Skills.pdf"
        section_4_file = "4-Section-4---Self-Discovery.pdf"
        section_5_file = "5-Section-5---21st-Century-Skills-Building-For-Teachers.pdf"
        section_6_file = "6-Section-6---Integrating-21st-Century-Skills-Into-Your-Classroom.pdf"
        section_7_file = "7-Thanks-To-Our-Teachers.pdf"

        # Introduction
        front_doc_node = DocumentNode(
            title="Introduction",
            description="Introduction",
            source_id=frontmatter_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, frontmatter_file),
                    language="en"
                )
            ])
        main_topic.add_child(front_doc_node)

        # Section 1
        section_1_doc_node = DocumentNode(
            title="Section 1",
            description="Section 1: Setting a Vision for Your 21st Century Learning Classroom",
            source_id=section_1_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_1_file),
                    language="en"
                )
            ])
        main_topic.add_child(section_1_doc_node)

        # Section 2
        section_2_topic = TopicNode(
            title="21st Century Mindsets & Practices", 
            source_id="21cs_section_2")

        section_2_doc_node = DocumentNode(
            title="21st Century Mindsets and Practices",
            description="21st Century Mindsets and Practices",
            source_id=section_2_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_doc_node)
        
        section_2_0_doc_node = DocumentNode(
            title="Mindset #1: Mindfulness",
            description="Mindset #1: Mindfulness",
            source_id=section_2_0_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_0_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_0_doc_node)
        
        section_2_1_doc_node = DocumentNode(
            title="Mindset #2: Curiousity",
            description="Mindset #2: Curiousity",
            source_id=section_2_1_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_1_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_1_doc_node)

        section_2_2_doc_node = DocumentNode(
            title="Mindset #3: Growth",
            description="Mindset #3: Growth",
            source_id=section_2_2_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_2_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_2_doc_node)

        section_2_3_doc_node = DocumentNode(
            title="Mindset #4: Empathy",
            description="Mindset #4: Empathy",
            source_id=section_2_3_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_3_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_3_doc_node)

        section_2_4_doc_node = DocumentNode(
            title="Mindset #5: Appreciation",
            description="Mindset #5: Appreciation",
            source_id=section_2_4_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_4_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_4_doc_node)

        section_2_5_doc_node = DocumentNode(
            title="Mindset #6: Experimentation",
            description="Mindset #6: Experimentation",
            source_id=section_2_5_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_5_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_5_doc_node)

        section_2_6_doc_node = DocumentNode(
            title="Mindset #7: Systems Thinking",
            description="Mindset #7: Systems Thinking",
            source_id=section_2_6_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_2_6_file),
                    language="en"
                )
            ])
        section_2_topic.add_child(section_2_6_doc_node)
        main_topic.add_child(section_2_topic)

        # Section 3
        section_3_doc_node = DocumentNode(
            title="Section 3",
            description="Section 3: 21st Century Skills",
            source_id=section_3_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_3_file),
                    language="en"
                )
            ])
        main_topic.add_child(section_3_doc_node)

        # Section 4
        section_4_doc_node = DocumentNode(
            title="Section 4",
            description="Section 4: Self Discovery",
            source_id=section_4_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_4_file),
                    language="en"
                )
            ])
        main_topic.add_child(section_4_doc_node)

        # Section 5
        section_5_doc_node = DocumentNode(
            title="Section 5",
            description="Section 5: 21st Century Skills Building For Teachers",
            source_id=section_5_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_5_file),
                    language="en"
                )
            ])
        main_topic.add_child(section_5_doc_node)

        # Section 6
        section_6_doc_node = DocumentNode(
            title="Section 6",
            description="Section 6: Integrating 21st Century Skills Into Your Classroom",
            source_id=section_6_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_6_file),
                    language="en"
                )
            ])
        main_topic.add_child(section_6_doc_node)

        # Section 7
        section_7_doc_node = DocumentNode(
            title="Section 7",
            description="Section 7: Thanks To Our Teachers",
            source_id=section_7_file,
            license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
            language="en",
            files=[
                DocumentFile(
                    path=os.path.join(SPLIT_PATH, section_7_file),
                    language="en"
                )
            ])
        main_topic.add_child(section_7_doc_node)

        # TODO(cpauya): English videos
        # TODO(cpauya): Burmese .pdf
        # TODO(cpauya): Burmese videos

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    chef = PointBChef()
    chef.main()
    # local_construct()
