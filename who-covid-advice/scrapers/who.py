from bs4 import BeautifulSoup

from ricecooker.classes import nodes


class WHOPageScraperBase:
    def __init__(self, url, file_on_disk):
        self.url = url
        self.file_on_disk = file_on_disk

    def node_for_text_section(self, content):
        # print("content = {}".format(content.prettify()))
        pass

    def node_for_video(self, content):
        pass

    def node_for_rows(self, rows):
        for row in rows:
            pass #print("row = {}".format(row.prettify()))

    def get_ricecooker_node(self):
        """
        Convert the data at the URL to a ricecooker/Kolibri-compatible representation.
        :return: A ricecooker.TreeNode-derived Node object.
        """

        raise NotImplementedError("Not implemented!")


class WHOCovidAdvicePageScraper(WHOPageScraperBase):
    def get_ricecooker_node(self):
        soup = BeautifulSoup(open(self.file_on_disk).read())

        print("opening {}".format(self.file_on_disk))

        # We'll add the title later when we iterate through the sections
        topic_node = nodes.TopicNode(source_id=self.url, title='')
        sections = soup.find_all('div', attrs={'class': 'section-heading'})
        for section in sections:
            # This is the top-level header, meaning it's the page title
            title = section.text.strip()
            if section.find('h1'):
                print("Page title = {}".format(title))
                topic_node.title = title
                continue

            print("Section = {}".format(title))

            content = section.find_next_sibling()
            if "content-block" in content.attrs['class']:
                self.node_for_text_section(content)
            elif "row" in content.attrs['class']:
                # the section rows are siblings in the tree.
                rows = [content]
                next = content.find_next_sibling()
                while "row" in next.attrs['class']:
                    rows.append(next)
                    next = next.find_next_sibling()

                self.node_for_rows(rows)

        return topic_node
