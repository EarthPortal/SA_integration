import argparse
from rdflib import Graph, Namespace, RDF, OWL
import requests

# Define namespaces
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

def main():
    parser = argparse.ArgumentParser(description="Compare and update TTL files based on skos:Collection owl:versionInfo.")
    parser.add_argument('--input', required=True, help='Path to the local TTL file')
    parser.add_argument('--url', required=True, help='URL to the remote TTL file with Turtle content negotiation')
    args = parser.parse_args()

    local_file = args.input
    remote_url = args.url

    # Load local TTL file
    local_graph = Graph()
    local_graph.parse(local_file, format="turtle")

    # Load remote TTL file using content negotiation
    headers = {
        "Accept": "text/turtle"
    }
    response = requests.get(remote_url, headers=headers)
    if response.status_code != 200:
        print(f"Error: Could not fetch remote TTL file from {remote_url} (status {response.status_code})")
        return
    remote_data = response.text

    remote_graph = Graph()
    remote_graph.parse(data=remote_data, format="turtle")

    # Find skos:Collection resources
    local_collections = set(local_graph.subjects(RDF.type, SKOS.Collection))
    remote_collections = set(remote_graph.subjects(RDF.type, SKOS.Collection))

    common_collections = local_collections & remote_collections

    update_required = False

    for collection in common_collections:
        local_versions = set(local_graph.objects(collection, OWL.versionInfo))
        remote_versions = set(remote_graph.objects(collection, OWL.versionInfo))

        print(f"Collection: {collection}")
        print(f"Local versionInfo: {list(local_versions)}")
        print(f"Remote versionInfo: {list(remote_versions)}")

        if local_versions != remote_versions:
            print("Version mismatch detected. Update required.")
            update_required = True
        else:
            print("Versions match.")
        print("---")

    # If versions differ, overwrite the local file with remote content
    if update_required:
        with open(local_file, 'w', encoding='utf-8') as f:
            f.write(remote_data)
        print(f"Local file '{local_file}' has been updated with content from {remote_url}")
    else:
        print("No update necessary. Local and remote versionInfo match.")

if __name__ == "__main__":
    main()
