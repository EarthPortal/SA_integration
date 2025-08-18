import requests
from rdflib import Graph, SKOS, RDF, URIRef, RDFS, Literal, BNode, Namespace
import argparse

# Base URL of the REST API
API_BASE_URL = "https://gcmd.earthdata.nasa.gov/kms/concepts/concept_scheme/"
CONCEPT_SCHEMES = [
    "ChainedOperations",
    "CollectionDataType",
    "ContactType",
    "CoordinateSystem",
    "DataFormat",
    "DatasetLanguage",
    "DatasetProgress",
    "DistributionSizeUnit",
    "DurationUnit", #?
    "GranuleSpatialRepresentation",
    "MeasurementName",
    "MetadataAssociationType",
    "MetadataLanguage",
    "MimeType",
    "MultimediaFormat",
    "Operations",
    "OrganizationPersonnelRole",
    "OrganizationType",
    "PersistentIdentifier",
    "PersonnelRole",
    "PhoneType",
    "PlatformType",
    "Private",
    "ProductFlag",
    "ProductLevelId",
    "ProjectionAuthority",
    "ProjectionDatumNames",
    "ProjectionName",
    "SpatialCoverageType", #?
    "chronounits",
    "discipline",
    "horizontalresolutionrange",
    "idnnode",
    "instruments",
    "isotopiccategory",
    "locations",
    "platforms",
    "projects",
    "providers",
    "rucontenttype",
    "sciencekeywords",
    "temporalresolutionrange",
    "verticalresolutionrange",
]

CONCEPT_SCHEMES_DTTR = [
    "DataFormat",
    "MeasurementName",
    "Operations",
    "PlatformType",
    "ProductLevelId",
    "ProjectionName",
    "discipline",
    "horizontalresolutionrange",
    "instruments",
    "isotopiccategory",
    "platforms",
    "sciencekeywords",
    "temporalresolutionrange",
    "verticalresolutionrange",
]

GCMD = Namespace("https://gcmd.earthdata.nasa.gov/kms#")

def fetch_rdf_from_api(base_url, concept_scheme):
    """
    Fetch RDF content from a paginated REST API and merge it into a single RDF Graph.

    Args:
        base_url (str): The base URL of the API.

    Returns:
        rdflib.Graph: A graph containing the merged RDF data.
    """
    merged_graph = Graph()
    page = 1
    session = requests.Session()  # Use a session for better performance
    print(f"Concept scheme: {concept_scheme}")
    while True:
        print(f"Fetching page {page}...")

        # Define query parameters
        params = {
            "format": "rdf",
            "page_num": page,
            "page_size": 2000
        }

        # Make the HTTP GET request
        response = session.get(base_url+concept_scheme, params=params, headers={"Accept": "application/rdf+xml"})

        if response.status_code != 200:
            print(f"Stopping fetch: Received status code {response.status_code} for page {page}.")
            break

        # Parse the RDF/XML content
        try:
            page_graph = Graph()
            page_graph.parse(data=response.text, format="application/rdf+xml")

            # for concept in page_graph.subjects(RDF.type, SKOS.Concept):
            #     if len(list(merged_graph.objects(concept, SKOS.broader))) == 0:
            #         merged_graph.add((concept, SKOS.broader, topConcept))

            # Merge the page's graph into the main graph
            merged_graph += page_graph

            print(f"Page {page} added successfully.")
        except Exception as e:
            print(f"Error parsing page {page}: {e}")
            break

        # Check if there is a next page (assumes API provides a mechanism, like a header or empty results)
        # if "next" not in response.links:  # Adjust based on API's pagination mechanism
        #     print("No more pages to fetch.")
        #     break

        page += 1
    
    # Find the blank node containing the ConceptScheme information and replace it with the proper ConceptScheme URI
    scheme_uri = URIRef(API_BASE_URL+concept_scheme)
    blank_node = None
    for s, p, o in merged_graph.triples((None, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), GCMD.gcmd)):
        if isinstance(s, BNode):
            blank_node = s
            break
    for s, p, o in merged_graph.triples((blank_node, None, None)):
        if p != GCMD.page_num and p != GCMD.page_size:
            merged_graph.add((scheme_uri, p, o))

    return merged_graph

def save_rdf_to_file(graph, file_path):
    """
    Save an RDF graph to a file.

    Args:
        graph (rdflib.Graph): The RDF graph to save.
        file_path (str): The path to the output file.
    """
    graph.serialize(destination=file_path, format="turtle")
    print(f"RDF data saved to {file_path}.")

def main():
    parser = argparse.ArgumentParser(description="Fetch and concatenate GCMD RDF data from the API.")
    parser.add_argument("--all", action='store_true', help="Compute all concept schemes and not just the ones of interest for Data Terra")
    parser.add_argument("--update", action='store_true', help="Force update the file, even if the version number did not change")
    args = parser.parse_args()

    # Fetch RDF data from the API
    schemes = args.all and CONCEPT_SCHEMES or CONCEPT_SCHEMES_DTTR
    merged_graph = Graph()
    session = requests.Session()
    response = session.get("https://gcmd.earthdata.nasa.gov/kms/concepts/root", params={}, headers={"Accept": "application/rdf+xml"})
    merged_graph.parse(data=response.text, format="application/rdf+xml")
    gcmd_scheme = URIRef("https://gcmd.earthdata.nasa.gov/kms/")
    merged_graph.add((gcmd_scheme, RDF.type, SKOS.ConceptScheme))
    for scheme in schemes:
        scheme_uri = URIRef(API_BASE_URL+scheme)
        merged_graph.add((scheme_uri, RDF.type, SKOS.ConceptScheme))
        topConcept = URIRef("")
        for concept in merged_graph.subjects(SKOS.inScheme, scheme_uri):
            topConcept = concept
            merged_graph.add((topConcept, SKOS.topConceptOf, scheme_uri))
            merged_graph.add((scheme_uri, SKOS.hasTopConcept, topConcept))
            merged_graph.add((topConcept, SKOS.topConceptOf, gcmd_scheme))
        merged_graph += fetch_rdf_from_api(API_BASE_URL, scheme)
        for s, p, o in merged_graph.triples((None, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), GCMD.gcmd)):
            if isinstance(s, BNode):
                blank_node = s
                for s2, p2, o2 in merged_graph.triples((blank_node, None, None)):
                    merged_graph.remove((s2, p2, o2))
    

    old_graph = Graph()
    old_file = args.all and "semantic_artefacts/gcmd_all.ttl" or "semantic_artefacts/gcmd_full.ttl"
    old_graph.parse(old_file, format="turtle")
    sciencekeywords = URIRef("https://gcmd.earthdata.nasa.gov/kms/concepts/concept_scheme/sciencekeywords")
    sciencekeywords_version = list(old_graph.objects(sciencekeywords, GCMD.keywordVersion))
    if len(sciencekeywords_version) == 0:
        sciencekeywords_version = "0.0"
    else:
        sciencekeywords_version = sciencekeywords_version[0]
    current_version = list(merged_graph.objects(sciencekeywords, GCMD.keywordVersion))[0]
    if not args.update and sciencekeywords_version == current_version:
        print("Version number did not change (", str(current_version), "), skipping save...")
    else:
        print("Current version:", str(current_version))
        save_rdf_to_file(merged_graph, old_file)

if __name__ == "__main__":
    main()