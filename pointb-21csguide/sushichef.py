#!/usr/bin/env python

import html
import os
import pprint
import requests

from bs4 import BeautifulSoup
from copy import copy
from PyPDF2 import PdfFileReader, PdfFileWriter

from ricecooker.chefs import SushiChef
from ricecooker.classes.files import DocumentFile, VideoFile
from ricecooker.classes.licenses import get_license
from ricecooker.classes.nodes import ChannelNode, DocumentNode, TopicNode, VideoNode
from ricecooker.utils.pdf import PDFParser

from pointb import PointBVideo

LE = 'Learning Equality'
LANG_CODE_EN = 'en'
LANG_CODE_MY = 'my'
LANG_CODES = (LANG_CODE_EN, LANG_CODE_MY,)

POINTB = 'Point B Design and Training'
POINTB_URL = 'http://www.pointb.is/'

DOWNLOADS_PATH = os.path.join(os.getcwd(), "downloads/")
DOWNLOADS_VIDEOS_PATH = os.path.join(DOWNLOADS_PATH, "videos/")
PDF_SPLIT_PATH_EN = os.path.join(DOWNLOADS_PATH, '21CSGuide_English_split/')
PDF_SPLIT_PATH_MY = os.path.join(DOWNLOADS_PATH, '21CSGuide_Myanmar_split/')

POINTB_PDF_URL = ''.join([POINTB_URL, 's/'])
CSGUIDE_PDF_EN = '21CSGuide_English.pdf'
CSGUIDE_PDF_EN_CROPPED = '21CSGuide_English_cropped.pdf'
CSGUIDE_PDF_MY = '21CSGuide_Myanmar.pdf'
CSGUIDE_PDF_MY_CROPPED = '21CSGuide_Myanmar_cropped.pdf'
PDF_URL_EN = ''.join([POINTB_PDF_URL, CSGUIDE_PDF_EN])
PDF_URL_MY = ''.join([POINTB_PDF_URL, CSGUIDE_PDF_MY])
PDF_PATH_EN = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN)
PDF_PATH_EN_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN_CROPPED)
PDF_PATH_MY = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY)
PDF_PATH_MY_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY_CROPPED)
PDFS = (
    {'pdf_url': PDF_URL_EN, 'pdf_path': PDF_PATH_EN},
    { 'pdf_url': PDF_URL_MY, 'pdf_path': PDF_PATH_MY },
)

VIDEO_URLS = { 
    LANG_CODE_EN: {
        'video_url': ''.join([POINTB_URL, '21cs-videos']), 
        'filename_prefix': 'pointb-video-%s-' % LANG_CODE_EN,
        'lang_code': LANG_CODE_EN,
        'download_path': os.path.join(os.getcwd(), DOWNLOADS_VIDEOS_PATH, LANG_CODE_EN, '')
        },
    LANG_CODE_MY: {
        'video_url': ''.join([POINTB_URL, '21cs-videos-mm']), 
        'filename_prefix': 'pointb-video-%s-' % LANG_CODE_MY,
        'lang_code': LANG_CODE_MY,
        'download_path': os.path.join(os.getcwd(), DOWNLOADS_VIDEOS_PATH, LANG_CODE_MY, '')
        }
    }

def split_chapters(lang_code=LANG_CODE_EN):
    """
    Splits the chapters for the English PDF.
    """
    if lang_code == LANG_CODE_EN:
        print('==> Splitting chapters for', PDF_PATH_EN_CROPPED)
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
                {'title': 'Mindset #7: Systems Thinking', 'page_start': 57, 'page_end': 61}
            ]
            },
            {'title': 'Section 3 - 21st Century Skills', 'page_start': 61, 'page_end': 69},
            {'title': 'Section 4 - Self-Discovery', 'page_start': 69, 'page_end': 95},
            {'title': 'Section 5 - 21st Century Skills Building For Teachers', 'page_start': 95, 'page_end': 109},
            {'title': 'Section 6 - Integrating 21st Century Skills Into Your Classroom', 'page_start': 109, 'page_end': 135},
            {'title': 'Thanks To Our Teachers', 'page_start': 135, 'page_end': 137},
        ]
        print('====> PDF_PATH_EN_CROPPED', PDF_PATH_EN_CROPPED, 'PDF_SPLIT_PATH_EN', PDF_SPLIT_PATH_EN)
        with PDFParser(PDF_PATH_EN_CROPPED, directory=PDF_SPLIT_PATH_EN) as pdfparser:
            chapters = pdfparser.split_subchapters(jsondata=page_ranges)
            # for chapter in chapters:
            #     print(chapter)
        print('==> DONE splitting chapters for English PDF.')

    if lang_code == LANG_CODE_MY:
        print('==> Splitting chapters for', PDF_PATH_MY_CROPPED)
        page_ranges = [
            {'title': 'Front Matter', 'page_start': 0, 'page_end': 13},
            {'title': 'Section 1 - Setting a Vision for Your 21st Century Learning Classroom', 'page_start': 13, 'page_end': 23},
            {'title': 'Section 2 - 21st Century Mindsets and Practices', 'page_start': 23, 'page_end': 61,
            'children': [
                {'title': 'Mindset #1: Mindfulness', 'page_start': 25, 'page_end': 33},
                {'title': 'Mindset #2: Curiousity', 'page_start': 33, 'page_end': 39},
                {'title': 'Mindset #3: Growth', 'page_start': 39, 'page_end': 43},
                {'title': 'Mindset #4: Empathy', 'page_start': 43, 'page_end': 49},
                {'title': 'Mindset #5: Appreciation', 'page_start': 49, 'page_end': 53},
                {'title': 'Mindset #6: Experimentation', 'page_start': 53, 'page_end': 59},
                {'title': 'Mindset #7: Systems Thinking', 'page_start': 59, 'page_end': 63}
            ]
            },
            {'title': 'Section 3 - 21st Century Skills', 'page_start': 63, 'page_end': 75},
            {'title': 'Section 4 - Self-Discovery', 'page_start': 75, 'page_end': 101},
            {'title': 'Section 5 - 21st Century Skills Building For Teachers', 'page_start': 101, 'page_end': 117},
            {'title': 'Section 6 - Integrating 21st Century Skills Into Your Classroom', 'page_start': 117, 'page_end': 143},
            {'title': 'Thanks To Our Teachers', 'page_start': 143, 'page_end': 145},
        ]
        print('====> PDF_PATH_MY_CROPPED', PDF_PATH_MY_CROPPED, 'PDF_SPLIT_PATH_MY', PDF_SPLIT_PATH_MY)
        with PDFParser(PDF_PATH_MY_CROPPED, directory=PDF_SPLIT_PATH_MY) as pdfparser:
            chapters = pdfparser.split_subchapters(jsondata=page_ranges)
            # for chapter in chapters:
            #     print(chapter)
        print('==> DONE splitting chapters for Burmese PDF.')
    return True


def download_pdfs():
    try:
        for pdf in PDFS:
            pdf_url = pdf['pdf_url']
            pdf_path = pdf['pdf_path']
            # Do not download if file already exists.
            if os.path.exists(pdf_path):
                print('==> PDF already exists, NOT downloading:', pdf_path)
            else:
                print('==> Downloading PDF', pdf_url, 'TO', pdf_path)
                response = requests.get(pdf_url)
                assert response.status_code == 200
                # save .pdf to the downloads folder
                with open(pdf_path, 'wb') as pdf_file:
                    pdf_file.write(response.content)
                print('... DONE downloading.')

            # crop from two-paged pdf into single-page pdf
            print('==> Cropping from two-page into single-page...', pdf_path)
            pdf_path_cropped = pdf_path.replace('.pdf', '_cropped.pdf')
            split_left_right_pages(pdf_path, pdf_path_cropped)

            # print_pdf_info(pdf_path_cropped)

            print('... DONE cropping.')

        return True
    except Exception as exc:
        print('==> ERROR downloading PDFs: ', exc)
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
    for nn, left_page in enumerate(page_ranges):
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
    pp = pprint.PrettyPrinter()
    pdf = PdfFileReader(open(pdf_path, "rb"))
    page_width, page_height = get_dimensions(pdf)
    print('==> PDF INFO:', page_width, page_height)
    num_pages = pdf.getNumPages()
    for page_num in range(0, num_pages):
        page = pdf.getPage(page_num)
        this_width = page.mediaBox.getUpperRight_x()
        this_height = page.mediaBox.getUpperRight_y()
        print('==> page', page_num, 'this_width',
              this_width, 'this_height', this_height)
        # pretty print the last 3 pages
        # if page_num + 3 >= num_pages:
        #     pp.pprint(page)


# TODO(cpauya): for testing, remove when done
def local_construct_pdfs():
    if not download_pdfs():
        print('==> Download of PDFS FAILED!')
        return False

    if not split_chapters(LANG_CODE_EN):
        print('==> Split chapters for English PDF FAILED!')
        return False

    if not split_chapters(LANG_CODE_MY):
        print('==> Split chapters for Burmese PDF FAILED!')
        return False

    # main_topic = TopicNode(title="English", source_id="pointb_en_main")

    # frontmatter_file = "0-Front-Matter.pdf"

    # # Introduction
    # front_doc_node = DocumentNode(
    #     title="Introduction",
    #     description="Introduction",
    #     source_id=frontmatter_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, frontmatter_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # main_topic.add_child(front_doc_node)
    return False


def scrape_video_data(url, lang_code, filename_prefix):
    """
    Scrapes videos based on the URL passed and returns a list of PointBVideo objects.
    For efficiency, the actual download will be done outside of this function, 
    after all video links have been collected.
    """
    video_data = []
    pp = pprint.PrettyPrinter()
    try:
        if lang_code in LANG_CODES:
            print('==> SCRAPING', url)
            response = requests.get(url)
            page = BeautifulSoup(response.text, 'html5lib')

            content_divs = page.find_all('div', class_='content-inner')
            for content_div in content_divs:
                video_block = content_div.find('div', class_='video-block')
                video_wrapper = video_block.find('div', class_='sqs-video-wrapper')
                data_html_raw = video_wrapper['data-html']
                data_html = html.unescape(data_html_raw)
                chunk = BeautifulSoup(data_html, 'html5lib')
                iframe = chunk.find('iframe')
                src = iframe['src']
                title = iframe['title']

                # print('==> SCRAPED VALUES')
                description = ''  # Get from the scraped page details
                block_html = content_div.find_all('div', class_='sqs-block html-block sqs-block-html')
                if isinstance(block_html, list) and len(block_html) > 1:
                    # Video description is the second div block.
                    desc_block = block_html[1]
                    block_content = desc_block.find('div', class_='sqs-block-content')
                    # print('==> BLOCK_CONTENT', block_content)
                    # NOTE: Some descriptions have <em> etc tags, some are separated by <br/> tags, while
                    # most are separated with <p> tags.  So we use `get_text(" ") - replacing those tags
                    # with " " and then stripping whitespaces for a "clean" description.`
                    description = block_content.get_text(" ", strip=True)
                    # print('==> DESCRIPTION', description)
                # print('==> url==', src)
                # print('==> title==', title)
                # print('==> description==', description)
                # print('==> DONE with SCRAPED VALUES')

                video = PointBVideo(
                            url=src, 
                            title=title, 
                            description=description, 
                            lang_code=lang_code,
                            filename_prefix=filename_prefix)
                video_data.append(video)

                # # TODO(cpauya): delete when done debugging
                # if len(video_data) > 0:
                #     break
    except Exception as e:
        print('==> Error scraping video URL', lang_code)
        pp.pprint(e)
    return video_data


def download_videos(lang_code):
    """
    Scrape, collect, and download the videos and their thumbnails.
    """
    video_data = []
    vinfo = VIDEO_URLS[lang_code]
    try:
        download_path = vinfo['download_path']
        video_data = scrape_video_data(
                            vinfo['video_url'], 
                            vinfo['lang_code'], 
                            vinfo['filename_prefix'])
        print('==> DOWNLOADING', download_path, '====> vinfo', vinfo)
        # Download video and metadata info for all video objects collected.
        for i, video in enumerate(video_data):
            progress = '%d/%d' % (i+1, len(video_data),)
            progress = '==> %s: Downloading video from %s ...' % (progress, video.url,)
            print(progress)
            if video.download(download_dir=download_path):
                # TODO(cpauya): Create VideoTopic then add to channel.
                pass
    except Exception as e:
        print('Error downloading videos:')
        pp = pprint.PrettyPrinter()
        pp.pprint(e)
        raise e
    print('==> DONE downloading videos for', vinfo)
    return video_data


# TODO(cpauya): for testing, remove when done
def local_construct_videos():
    """
    """
    video_data = download_videos()
    if not video_data:
        print('==> Download of Videos FAILED!')
        return False

    main_topic = TopicNode(title="English", source_id="pointb_en_main")

    # TODO(cpauya: VideoNode constructor has no argument for language code?
    for i, video in enumerate(video_data):
        # # TODO(cpauya): Remove when done testing
        # if i > 0:
        #     break
        filepath = os.path.join(DOWNLOADS_VIDEOS_PATH, video.filepath)
        video_node = VideoNode(
                source_id=video.uid, 
                title=video.title, 
                description=video.description,
                thumbnail=video.thumbnail,
                license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
                files=[
                    VideoFile(
                        path=filepath,
                        language=LANG_CODE_EN
                    )
                ])
        main_topic.add_child(video_node)
        print('====> VIDEO INFO', video.thumbnail, video.filepath)

    return main_topic


def build_english_video_topics(topic):
    """
    """
    video_data = download_videos(LANG_CODE_EN)
    if not video_data:
        print('==> Download of Videos FAILED!')
        return False

    # TODO(cpauya: VideoNode constructor has no argument for language code?
    for i, video in enumerate(video_data):
        # TODO(cpauya): Remove when done testing
        # if i > 0:
        #     break
        # print('==> video', video)
        filepath = video.filepath
        video_node = VideoNode(
                source_id=video.uid, 
                title=video.title, 
                description=video.description,
                aggregator=LE,
                thumbnail=video.thumbnail,
                license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
                files=[
                    VideoFile(
                        path=filepath,
                        language=LANG_CODE_EN
                    )
                ])
        topic.add_child(video_node)

    return topic


def build_burmese_video_topics(topic):
    """
    """
    video_data = download_videos(LANG_CODE_MY)
    if not video_data:
        print('==> Download of Videos FAILED!')
        return False

    for i, video in enumerate(video_data):
        # TODO(cpauya): Remove when done testing
        # if i > 0:
        #     break
        # print('==> video', video)
        filepath = video.filepath
        video_node = VideoNode(
                source_id=video.uid, 
                title=video.title, 
                description=video.description,
                aggregator=LE,
                thumbnail=video.thumbnail,
                license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
                files=[
                    VideoFile(
                        path=filepath,
                        language=LANG_CODE_MY
                    )
                ])
        topic.add_child(video_node)
    return topic


def build_english_pdf_topics(main_topic):

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
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, frontmatter_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(front_doc_node)

    # Section 1
    section_1_doc_node = DocumentNode(
        title="Section 1: Setting a Vision for Your 21st Century Learning Classroom",
        description="Section 1: Setting a Vision for Your 21st Century Learning Classroom",
        source_id=section_1_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_1_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(section_1_doc_node)

    # Section 2
    section_2_topic = TopicNode(
        title="21st Century Mindsets & Practices",
        source_id="pointb_section_2")

    section_2_doc_node = DocumentNode(
        title="21st Century Mindsets and Practices",
        description="21st Century Mindsets and Practices",
        source_id=section_2_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_doc_node)

    section_2_0_doc_node = DocumentNode(
        title="Mindset #1: Mindfulness",
        description="Mindset #1: Mindfulness",
        source_id=section_2_0_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_0_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_0_doc_node)

    section_2_1_doc_node = DocumentNode(
        title="Mindset #2: Curiousity",
        description="Mindset #2: Curiousity",
        source_id=section_2_1_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_1_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_1_doc_node)

    section_2_2_doc_node = DocumentNode(
        title="Mindset #3: Growth",
        description="Mindset #3: Growth",
        source_id=section_2_2_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_2_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_2_doc_node)

    section_2_3_doc_node = DocumentNode(
        title="Mindset #4: Empathy",
        description="Mindset #4: Empathy",
        source_id=section_2_3_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_3_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_3_doc_node)

    section_2_4_doc_node = DocumentNode(
        title="Mindset #5: Appreciation",
        description="Mindset #5: Appreciation",
        source_id=section_2_4_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_4_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_4_doc_node)

    section_2_5_doc_node = DocumentNode(
        title="Mindset #6: Experimentation",
        description="Mindset #6: Experimentation",
        source_id=section_2_5_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_5_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_5_doc_node)

    section_2_6_doc_node = DocumentNode(
        title="Mindset #7: Systems Thinking",
        description="Mindset #7: Systems Thinking",
        source_id=section_2_6_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_2_6_file),
                language=LANG_CODE_EN
            )
        ])
    section_2_topic.add_child(section_2_6_doc_node)
    main_topic.add_child(section_2_topic)

    # Section 3
    section_3_doc_node = DocumentNode(
        title="Section 3: 21st Century Skills",
        description="Section 3: 21st Century Skills",
        source_id=section_3_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_3_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(section_3_doc_node)

    # Section 4
    section_4_doc_node = DocumentNode(
        title="Section 4: Self Discovery",
        description="Section 4: Self Discovery",
        source_id=section_4_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_4_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(section_4_doc_node)

    # Section 5
    section_5_doc_node = DocumentNode(
        title="Section 5: 21st Century Skills Building For Teachers",
        description="Section 5: 21st Century Skills Building For Teachers",
        source_id=section_5_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_5_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(section_5_doc_node)

    # Section 6
    section_6_doc_node = DocumentNode(
        title="Section 6: Integrating 21st Century Skills Into Your Classroom",
        description="Section 6: Integrating 21st Century Skills Into Your Classroom",
        source_id=section_6_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_6_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(section_6_doc_node)

    # Section 7
    section_7_doc_node = DocumentNode(
        title="Section 7: Thanks To Our Teachers",
        description="Section 7: Thanks To Our Teachers",
        source_id=section_7_file,
        license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH_EN, section_7_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(section_7_doc_node)
    return main_topic


def build_burmese_pdf_topics(topic):

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

    LICENSE = get_license("CC BY-NC-SA", copyright_holder=POINTB)
    
    lang_code = LANG_CODE_MY
    if lang_code == LANG_CODE_EN:
        pdf_split_path = PDF_PATH_EN
    elif lang_code == LANG_CODE_MY:
        pdf_split_path = PDF_PATH_MY

    PDF_TOPICS = {
        lang_code: {
            'introduction': {
                'title': 'Introduction',
                'description': 'Introduction',
                'source_id': '%s-%s' % (frontmatter_file, lang_code,),
                'license': LICENSE,
                'language': lang_code,
                'files': [
                    DocumentFile(
                        path=os.path.join(pdf_split_path, frontmatter_file), 
                        language=lang_code
                    )
                ]
            },
        }
    }

    # Introduction
    intro_dict = PDF_TOPICS[lang_code]['introduction']
    front_doc_node = DocumentNode(**intro_dict)
    topic.add_child(front_doc_node)

    # # Section 1
    # section_1_doc_node = DocumentNode(
    #     title="Section 1: Setting a Vision for Your 21st Century Learning Classroom",
    #     description="Section 1: Setting a Vision for Your 21st Century Learning Classroom",
    #     source_id=section_1_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_1_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # topic.add_child(section_1_doc_node)

    # # Section 2
    # section_2_topic = TopicNode(
    #     title="21st Century Mindsets & Practices",
    #     source_id="pointb_section_2")

    # section_2_doc_node = DocumentNode(
    #     title="21st Century Mindsets and Practices",
    #     description="21st Century Mindsets and Practices",
    #     source_id=section_2_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_doc_node)

    # section_2_0_doc_node = DocumentNode(
    #     title="Mindset #1: Mindfulness",
    #     description="Mindset #1: Mindfulness",
    #     source_id=section_2_0_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_0_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_0_doc_node)

    # section_2_1_doc_node = DocumentNode(
    #     title="Mindset #2: Curiousity",
    #     description="Mindset #2: Curiousity",
    #     source_id=section_2_1_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_1_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_1_doc_node)

    # section_2_2_doc_node = DocumentNode(
    #     title="Mindset #3: Growth",
    #     description="Mindset #3: Growth",
    #     source_id=section_2_2_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_2_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_2_doc_node)

    # section_2_3_doc_node = DocumentNode(
    #     title="Mindset #4: Empathy",
    #     description="Mindset #4: Empathy",
    #     source_id=section_2_3_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_3_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_3_doc_node)

    # section_2_4_doc_node = DocumentNode(
    #     title="Mindset #5: Appreciation",
    #     description="Mindset #5: Appreciation",
    #     source_id=section_2_4_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_4_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_4_doc_node)

    # section_2_5_doc_node = DocumentNode(
    #     title="Mindset #6: Experimentation",
    #     description="Mindset #6: Experimentation",
    #     source_id=section_2_5_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_5_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_5_doc_node)

    # section_2_6_doc_node = DocumentNode(
    #     title="Mindset #7: Systems Thinking",
    #     description="Mindset #7: Systems Thinking",
    #     source_id=section_2_6_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_2_6_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # section_2_topic.add_child(section_2_6_doc_node)
    # topic.add_child(section_2_topic)

    # # Section 3
    # section_3_doc_node = DocumentNode(
    #     title="Section 3: 21st Century Skills",
    #     description="Section 3: 21st Century Skills",
    #     source_id=section_3_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_3_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # topic.add_child(section_3_doc_node)

    # # Section 4
    # section_4_doc_node = DocumentNode(
    #     title="Section 4: Self Discovery",
    #     description="Section 4: Self Discovery",
    #     source_id=section_4_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_4_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # topic.add_child(section_4_doc_node)

    # # Section 5
    # section_5_doc_node = DocumentNode(
    #     title="Section 5: 21st Century Skills Building For Teachers",
    #     description="Section 5: 21st Century Skills Building For Teachers",
    #     source_id=section_5_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_5_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # topic.add_child(section_5_doc_node)

    # # Section 6
    # section_6_doc_node = DocumentNode(
    #     title="Section 6: Integrating 21st Century Skills Into Your Classroom",
    #     description="Section 6: Integrating 21st Century Skills Into Your Classroom",
    #     source_id=section_6_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_6_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # topic.add_child(section_6_doc_node)

    # # Section 7
    # section_7_doc_node = DocumentNode(
    #     title="Section 7: Thanks To Our Teachers",
    #     description="Section 7: Thanks To Our Teachers",
    #     source_id=section_7_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder=POINTB),
    #     language=LANG_CODE_EN,
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH_EN, section_7_file),
    #             language=LANG_CODE_EN
    #         )
    #     ])
    # topic.add_child(section_7_doc_node)
    return topic


class PointBChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "PointB 21CS Guide",
        # where you got the content (change me!!)
        "CHANNEL_SOURCE_DOMAIN": "pointb.is",
        # channel's unique id (change me!!) # TODO(cpauya): remove 'test-'
        "CHANNEL_SOURCE_ID": "test-21csguide",
        "CHANNEL_LANGUAGE": "mul",  # le_utils language code
        "CHANNEL_THUMBNAIL": None,  # TODO(cpauya): set thumbnail
        # (optional)
        "CHANNEL_DESCRIPTION": "Guide To Becoming A 21St Century Teacher",
    }

    def construct_channel(self, **kwargs):

        if not download_pdfs():
            print('==> Download of PDFS FAILED!')
            return False

        if not split_chapters(lang_code=LANG_CODE_EN):
            print('==> Split chapters for English PDF FAILED!')
            return False

        channel = self.get_channel(**kwargs)

        # English topics
        main_topic = TopicNode(title="English", source_id="pointb_en_main")
        topic_guide = TopicNode(title="21st Century Guide", source_id="pointb_en_topic")
        topic_videos_en = TopicNode(title="Videos", source_id="pointb_en_videos")
        main_topic.add_child(topic_guide)
        main_topic.add_child(topic_videos_en)

        # Burmese topics
        main_topic_my = TopicNode(title="Burmese", source_id="pointb_my_main")
        topic_guide_my = TopicNode(title="21st Century Guide", source_id="pointb_my_guide")
        topic_videos_my = TopicNode(title="Videos", source_id="pointb_my_videos")
        main_topic_my.add_child(topic_guide_my)
        main_topic_my.add_child(topic_videos_my)

        channel.add_child(main_topic)
        channel.add_child(main_topic_my)

        main_topic = build_english_pdf_topics(topic_guide)
        # TODO(cpauya): Burmese .pdfs
        main_topic = build_burmese_pdf_topics(topic_guide)
        # # TODO(cpauya): English videos
        # topic = build_english_video_topics(topic_videos_en)
        # # TODO(cpauya): Burmese videos
        # topic = build_burmese_video_topics(topic_videos_my)

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    chef = PointBChef()
    chef.main()
    # local_construct_pdfs()
    # local_construct_videos()
