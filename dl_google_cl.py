import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import time
import re
import random

current_proxy_index = 0

def get_proxies(mode='direct'):
    load_dotenv()
    proxy_api_key = os.getenv("PROXY_API_KEY")

    proxy_api_url = "https://proxy.webshare.io/api/v2/proxy/list/"
    
    headers = {"Authorization": f"Token {proxy_api_key}"}
    params = {"mode": mode}

    response = requests.get(proxy_api_url, headers=headers, params=params)

    # Check the response status code
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        print("Response:", response.text)
        return []

    proxy_data = response.json()
    # print("Full API Response:", proxy_data)  # Log the full response


    if 'results' in proxy_data:
        if mode == 'direct':
            return [f"http://{proxy['username']}:{proxy['password']}@{proxy['proxy_address']}:{proxy['port']}" for proxy in proxy_data['results']]
        elif mode == 'backbone':
            return [f"http://{proxy['username']}:{proxy['password']}@p.webshare.io:{proxy['port']}" for proxy in proxy_data['results']]
    else:
        print("Key 'results' not found in the response")
        return []

def get_text_links(url, proxies, session):
    global current_proxy_index  # Use the global index
    print(current_proxy_index)
    # Check if there are proxies in the list
    if not proxies:
        print("No proxies available.")
        return "", []

    # Rotate proxies
    proxy = proxies[current_proxy_index]  # Use the current proxy
    session.proxies.update({'http': proxy, 'https': proxy})
    current_proxy_index = (current_proxy_index + 1) % len(proxies)  # Update the index for next use

    links = []
    all_text = ''

    try:
        response = session.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            all_text = soup.get_text(separator=' ', strip=True)
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    links.append(href)
            time.sleep(1)
    except requests.RequestException as e:
        print(f"Error during requests to {url}: {str(e)}")

    return all_text, links, soup


def parse_links(links):
    prefix = 'https://scholar.google.com/'

    filtered_and_modified_list = [
        prefix + item if '/scholar_case?case=' in item and not item.startswith('https://') else item
        for item in links if '/scholar_case?case=' in item
    ]

    new_links = list(set(filtered_and_modified_list))

    return new_links


def process_citation(citation):
    """
    Process a legal citation by:
    1. Checking for and removing '<BEST_CASE:>' prefix if present.
    2. Replacing 'v.' with 'v'.
    3. Separating the citation by comma.
    4. Removing any content within parentheses.
    
    Args:
    citation (str): The legal citation to be processed.

    Returns:
    list: A list of processed components of the citation, excluding parenthetical parts.
    """
    # Check for and remove '<BEST_CASE:>' prefix
    prefix = '<BEST_CASE:>'
    if citation.startswith(prefix):
        citation = citation[len(prefix):].strip()

    # Replace 'v.' with 'v'
    citation = citation.replace('v.', 'v')

    # Split by comma
    parts = citation.split(',')

    # Process each part to remove content within parentheses
    processed_parts = []
    for part in parts:
        # Trim whitespace
        part = part.strip()

        # Remove content within parentheses
        if '(' in part and ')' in part:
            start = part.find('(')
            end = part.find(')')
            non_parenthetical = part[:start].strip()
            # Add non-empty parts to the list
            if non_parenthetical:
                processed_parts.append(non_parenthetical)
        else:
            processed_parts.append(part)

    return processed_parts


def get_citation_url(citation, soup):
    processed_citation = process_citation(citation)

    print(process_citation)

    for a_tag in soup.find_all('a'):
        if any(citation_part in a_tag.get_text() for citation_part in processed_citation):
            link = a_tag['href']
            return 'https://scholar.google.com' + link

    return None

def create_link_query(input_string, prefix='https://scholar.google.com/scholar?hl=en&as_sdt=6%2C33&q='):
    """
    Function to convert a string into a structured link query.

    :param input_string: The input string to be converted.
    :param prefix: The prefix for the link, default is set to Google Scholar.
    :return: A structured link query.
    """
    # Split the input string into words and join them with '+'
    query = '+'.join(input_string.split())
    # Combine the prefix and the query to form the full link
    full_link = prefix + query
    return full_link


def parse_query_url(url, proxies, session):

    global current_proxy_index  # Use the global index
    print(current_proxy_index)
    # Check if there are proxies in the list
    if not proxies:
        print("No proxies available.")
        return "", []

    # Rotate proxies
    proxy = proxies[current_proxy_index]  # Use the current proxy
    session.proxies.update({'http': proxy, 'https': proxy})
    current_proxy_index = (current_proxy_index + 1) % len(proxies)  # Update the index for next use


    # Send an HTTP GET request to the URL
    response = requests.get(url)
    
    soup = BeautifulSoup(response.text, 'html.parser')

    # Extracting case names and links
    cases = []
    for case in soup.find_all('div', class_='gs_ri'):
        case_name = case.find('h3', class_='gs_rt').get_text()
        case_link = case.find('a')['href']
        cases.append((case_name, case_link))
        
    return cases

def count_case_appearances(input_list):
    # Flatten the list of lists
    flat_list = [item for sublist in input_list for item in sublist]

    # Count appearances and store one link per case using a dictionary
    count_dict = {}
    for case, link in flat_list:
        if case in count_dict:
            # Increment the count, keep the existing link
            count, _ = count_dict[case]
            count_dict[case] = (count + 1, link)
        else:
            # New case, set count to 1 and store the link
            count_dict[case] = (1, link)

    # Create a list of tuples (case, link, count) from the dictionary
    counted_list = [(case, link, count) for case, (count, link) in count_dict.items()]

    # Sort the list based on the count in descending order
    sorted_counted_list = sorted(counted_list, key=lambda x: x[2], reverse=True)

    return sorted_counted_list


def get_cases_from_queries(queries, proxies, session):
    # list of all the cases that appear
    all_cases = []
    # list of top three (3) most relevant cases for each search
    top_cases = []

    for query in queries:
        query_url = create_link_query(query)
        time.sleep(2.5)
        potential_cases = parse_query_url(query_url,proxies=proxies,session=session)
        all_cases.append(potential_cases)
        top_cases.append(potential_cases[:3])

    return all_cases, top_cases


def get_relevant_searches(queries, proxies, session, num_cases=6):

    all_cases, top_cases = get_cases_from_queries(queries, proxies, session)

    # flatten top_cases
    top_cases = [item for sublist in top_cases for item in sublist]
    # sort all_cases
    sorted_cases = count_case_appearances(all_cases)

    # Start with cases that have more than one occurrence
    search_list = [case for case in sorted_cases if case[2] > 1]

    if len(search_list) <= num_cases:
        case_names = [item[0] for item in search_list]
        remaining_top_cases = [case for case in top_cases if case[0] not in case_names]

        num_indices = min(num_cases-len(search_list), len(remaining_top_cases))
        unique_indices = random.sample(range(len(remaining_top_cases)), num_indices)
        for idx in unique_indices:
            search_list.append(remaining_top_cases[idx])

    return search_list
