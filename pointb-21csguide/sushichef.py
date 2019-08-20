#!/usr/bin/env python

from PyPDF2 import PdfFileReader, PdfFileWriter

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license


def download_pdfs():
    pass  # See notebooks/ 1. Download PDFs


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
    """
    pdfin1 = PdfFileReader(open(pdfin_path, "rb"))  # used for left pages
    pdfin2 = PdfFileReader(open(pdfin_path, "rb"))  # used for right pages
    pdfout = PdfFileWriter()

    page_width, page_height = get_dimensions(pdfin1)

    num_pages = pdfin1.getNumPages()
    for page_num in range(0, num_pages):
        left_page = pdfin1.getPage(page_num)
        this_width = left_page.mediaBox.getUpperRight_x()

        if this_width > float(page_width) + 20:
            # print(page_num, 'wide')

            left_page = pdfin1.getPage(page_num)
            left_page.cropBox.upperRight = (page_width, page_height)
            left_page.trimBox.upperRight = (page_width, page_height)
            pdfout.addPage(left_page)

            right_page = pdfin2.getPage(page_num)
            right_page.cropBox.lowerLeft = (page_width, 0)
            right_page.trimBox.lowerLeft = (page_width, 0)
            pdfout.addPage(right_page)

        else:
            # print(page_num, 'normal')
            pdfout.addPage(left_page)

    # save outpout PDF result
    with open(pdfout_path, "wb") as out_f:
        pdfout.write(out_f)


class PointBChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "PointB 21CS Guide",
        "CHANNEL_SOURCE_DOMAIN": "pointb.is",  # where you got the content (change me!!)
        "CHANNEL_SOURCE_ID": "21csguide",  # channel's unique id (change me!!)
        "CHANNEL_LANGUAGE": "mul",  # le_utils language code
        "CHANNEL_THUMBNAIL": None,  # TODO:
        "CHANNEL_DESCRIPTION": "What is this channel about?",  # (optional)
    }

    def construct_channel(self, **kwargs):
        channel = self.get_channel(**kwargs)
        potato_topic = TopicNode(title="Potatoes!", source_id="<potatos_id>")
        channel.add_child(potato_topic)
        doc_node = DocumentNode(
            title="Growing potatoes",
            description="An article about growing potatoes on your rooftop.",
            source_id="pubs/mafri-potatoe",
            license=get_license("CC BY", copyright_holder="University of Alberta"),
            language="en",
            files=[
                DocumentFile(
                    path="https://www.gov.mb.ca/inr/pdf/pubs/mafri-potatoe.pdf",
                    language="en",
                )
            ],
        )
        potato_topic.add_child(doc_node)
        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    chef = PointBChef()
    chef.main()
