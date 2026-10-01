import xml.etree.ElementTree as ET
tree = ET.parse('report.xml')
root = tree.getroot()
for testcase in root.iter('testcase'):
    for failure in testcase.iter('failure'):
        print(f"{testcase.attrib['name']} failed:")
        print(failure.attrib.get('message', ''))
        print('---')
