import awa2el_index as index
import csv

with open('awa2el.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(["URL", "title", "breadcrumb1", "breadcrumb2", "breadcrumb3", "breadcrumb4",
                     "PDFname1", "PDFname2", "PDFname3", "PDFname4"])
    for grade in index.graderange:
        for item in index.SearchResults(index.BASE_URL.format(grade)).get_results():
            d = item.details()
            assert len(d.breadcrumbs) < 5
            assert len(d.pdf_names) < 5
            d.breadcrumbs.extend(["", "", "", ""])
            b1, b2, b3, b4 = d.breadcrumbs[:4]
            d.pdf_names.extend(["", "", "", ""])
            p1, p2, p3, p4 = d.pdf_names[:4]
            print ('\t'.join([d.url, d.title, b1, b2, b3, b4, p1, p2, p3, p4]))
            writer.writerow([d.url, d.title, b1, b2, b3, b4, p1, p2, p3, p4])

