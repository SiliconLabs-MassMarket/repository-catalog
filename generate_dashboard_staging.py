
import os
import sys
import requests
from jinja2 import Environment, FileSystemLoader
from github import Github
from datetime import datetime
import re
from collections import Counter
import json

curdir = os.path.dirname(os.path.abspath(__file__))

PAT_TOKEN = sys.argv[1]
TEST_BRANCH = sys.argv[2]

api_headers = {
    'Authorization': f'token {PAT_TOKEN}',
    'Accept': 'application/vnd.github.v3.raw'
}

excluded = {'.github', 'deprecated', 'doc'}
##################################################################

def split_repo_info(repo_url):
	url_split = repo_url.split("/")
	owner = url_split[3]
	repo_name = url_split[4]

	return owner, repo_name

"""
Function to got the latest date commit of a repo
"""
def got_last_update(repo_url):
	owner, repo = split_repo_info(repo_url)

	# GitHub API URL to get the latest commits
	url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"

	# Send GET request to GitHub API
	response = requests.get(url, headers=api_headers)

	# Parse JSON response
	if response.status_code == 200:
		data = response.json()
		latest_commit_date = data[0]['commit']['committer']['date']
		datetime_obj = datetime.fromisoformat(str(latest_commit_date))
		date_yymmdd = datetime_obj.date()     
		# print("Latest update date:", date_yymmdd)
		return date_yymmdd
	else:
		print(80*"*")
		print("===> Error: Could not got the latest date of repo: ", repo)
		print(url)
		sys.exit(1)

def count_file_extensions(owner, repo, branch, extension):
	"""Fetch all file extensions in a GitHub repo using the Git Trees API."""
	api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
	headers = {'Accept': 'application/vnd.github.v3+json'}
	response = requests.get(api_url, headers=headers)

	if response.status_code != 200:
		raise Exception(f"GitHub API error: {response.status_code} - {response.text}")

	data = response.json()
	files = [item['path'] for item in data.get('tree', []) if item['type'] == 'blob']
	extensions = [f.split('.')[-1] for f in files if '.' in f]

	for ext, count in Counter(extensions).items():
		# print(f".{ext}: {count}")    
		if ext == extension:
			return count
		
def got_number_examples(repo_url, scan_in_folder, default_branch):
	owner, repo = split_repo_info(repo_url)

	# If repo contain templates.xml then scan .slcp files
	if repo.find("energy_harvesting_applications") != -1:
		# url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/energy_harvesting_templates.xml"
		url = f'https://api.github.com/repos/{owner}/{repo}/contents/energy_harvesting_templates.xml?ref={default_branch}'
	else:
		# url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/templates.xml"
		url = f'https://api.github.com/repos/{owner}/{repo}/contents/templates.xml?ref={default_branch}'
	# print(url)
	response = requests.get(url, headers=api_headers)
	if response.status_code == 200:	
		contents = response.text
		headers = re.findall(r'.slcp', contents)
		total_examples = len(headers)
		
		return total_examples


	# If repo did not contain templates.xml
	url = f"https://api.github.com/repos/{owner}/{repo}/contents/{scan_in_folder}"

	# Send GET request to GitHub API
	response = requests.get(url, headers=api_headers)

	# Parse JSON response
	if response.status_code == 200:
		contents = response.json()
		
		subfolders = [
			item for item in contents
			if item['type'] == 'dir' and item['name'] not in excluded
		]
		total_examples = len(subfolders)
		return total_examples
		# print("Number of subfolders:", len(subfolders))
	else:
		print(80*"*")
		print("===> Failed in got_number_examples() for {0} with code :{1}".format(repo, response.status_code))
		print(url)
		sys.exit(1)

"""

"""
def got_latest_release(repo_url):
	owner, repo = split_repo_info(repo_url)
	# GitHub API URL to get the latest release
	url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

	# Send GET request to GitHub API
	response = requests.get(url, headers=api_headers)

	# Parse JSON response
	latest_version = ""
	if response.status_code == 200:
		data = response.json()
		latest_version = data['tag_name']
		
		# print("Latest release version:", latest_version)
	else:
		print(80*"*")
		print("Failed in got_latest_release() for repo {0} with code: {1}".format(repo, response.status_code))	
		print(url)
	
	return latest_version

def check_branch_existing(owner, repo, branch, token=None):
	"""
	Check if branch exists using PyGithub library
	"""
	try:
		g = Github(token) if token else Github()
		repository = g.get_repo(f"{owner}/{repo}")
		
		# Try to get the branch
		repository.get_branch(branch)
		return True
		
	except Exception as e:
		if "Branch not found" in str(e) or "404" in str(e):
			return False
		else:
			print(f"Error: {e}")
			return False

# Install with: pip install PyGithub
########################################################################################################
########################################################################################################
repositories = []
def got_repositories():
	json_file = os.path.join(curdir, "data/repository_info_staging.json")
	with open(json_file, "r") as f:
		json_data = json.load(f)

	for id in range(0, len(json_data)):			
		# Passing value into dict            
		repo_url = json_data[id]["url"]
		scan_in_folder = json_data[id]["examples_folder"]
		owner, repo = split_repo_info(repo_url)

		check_branch = check_branch_existing(owner, repo, TEST_BRANCH, PAT_TOKEN)
		if check_branch == False:
			default_branch = got_default_branch(owner, repo)
		else:
			default_branch = TEST_BRANCH

		if scan_in_folder != "not_check":
			num_examples = got_number_examples(repo_url, scan_in_folder, default_branch)
		else:
			extension = json_data[id]["extension"]
			num_examples = count_file_extensions(owner, repo, default_branch, extension)

		last_update = got_last_update(repo_url)
		release_ver = got_latest_release(repo_url)
		new_repo = {
			'no': id,
			'repo_name': json_data[id]["name"],
			'repo_url': repo_url,
			'tech': json_data[id]["tech"],
			'num_examples': num_examples,
			'last_update': str(last_update),
			'release_ver': release_ver,
		}
		repositories.append(new_repo)


########################################################################################################
########################################################################################################
def got_example_folder(repo_name, scan_in_folder, branch=None):
	# Create a GitHub instance with authentication for private repos
	g = Github(PAT_TOKEN)
	# Get the repository
	repo = g.get_repo(repo_name)
	# Get contents in scan_in_folder directory from specific branch
	if branch:
		contents = repo.get_contents(scan_in_folder, ref=branch)
	else:
		contents = repo.get_contents(scan_in_folder)
	# List folder names
	folders = [item.name for item in contents if item.type == "dir" and item.name not in excluded]
	print("Total example:", len(folders))
	return folders

def get_readme_headers(owner, repo, default_branch, folder):
	# url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{folder}/README.md"
	url = f'https://api.github.com/repos/{owner}/{repo}/contents/{folder}/README.md?ref={default_branch}'
	response = requests.get(url, headers=api_headers)
	if response.status_code == 200:
		content = response.text
		# Extract level 1 headers (lines starting with exactly one '#')
		headers = re.findall(r'(?m)^# (.+)', content)
		headers_content = headers[0].replace("#", "")
		return headers_content
	else:
		print("Failed to passing API in get_readme_headers() for: {0}, folder: {1}".format(repo, folder))
		# print(f"Could not found level 1 headers (#) in README.md from {folder}")
		sys.exit(1)

def got_default_branch(owner, repo):
	url = f"https://api.github.com/repos/{owner}/{repo}"
	response = requests.get(url, headers=api_headers)

	if response.status_code == 200:
		data = response.json()
		default_branch = data.get("default_branch")
		return default_branch
		
	else:
		print(f"Failed to passing API in got_default_branch() for repo:", repo)
		sys.exit(1)

def got_type_shield_io(owner, repo, default_branch, folder):
	url = f'https://api.github.com/repos/{owner}/{repo}/contents/{folder}/README.md?ref={default_branch}'
	response = requests.get(url, headers=api_headers)
	if response.status_code == 200:
		content = response.text
		try:
			headers = re.findall(r'\!\[Type badge\]\(https://img.shields.io/badge/(.+?)-salmon', content, re.MULTILINE | re.DOTALL)
			# Replace %20 with spaces for all matches and return the list
			shield_types = [header.replace("%20", " ") for header in headers]
			return shield_types
		except Exception as e:
			print(f"Error parsing content: {e}")
			return []
	else:
		print("Failed to passing API in got_type_shield_io() for repo: {0}, folder: {1}".format(repo, folder))
		return []


examples = []
def got_example_shield():
	json_file = os.path.join(curdir, "data/repository_info_staging.json")
	with open(json_file, "r") as f:
		json_data = json.load(f)

	for id in range(0, len(json_data)):			
		# Passing value into dict            
		repo_url = json_data[id]["url"]
		scan_in_folder = json_data[id]["examples_folder"]
		# repo not follow AEP format so README.md did not have GH Shield
		if scan_in_folder == "not_check":
			continue

		owner, repo = split_repo_info(repo_url)
		repo_name = owner + "/" + repo
		print(80*"*")
		print("Checking for repo:", repo_name)

		
		check_branch = check_branch_existing(owner, repo, TEST_BRANCH, PAT_TOKEN)
		if check_branch == False:
			default_branch = got_default_branch(owner, repo)
		else:
			default_branch = TEST_BRANCH

		print(f"Checking for branch: {default_branch}")
		folders = got_example_folder(repo_name, scan_in_folder, default_branch)

		for folder in folders:
			if scan_in_folder != None:
				folder = scan_in_folder + "/" + folder

			list_app_type_shield = got_type_shield_io(owner, repo, default_branch, folder)
			
			
			if len(list_app_type_shield) > 0:
				readme_header = get_readme_headers(owner, repo, default_branch, folder)
			else:
				# If README.md did not have App Type shield then ignore
				continue

			app_url = "https://github.com/" + repo_name + "/blob/" + default_branch + "/" + folder + "/README.md"
			example_name = readme_header
			example_url = app_url
			
			for app_type in list_app_type_shield:
				new_example = {
					'example_name': example_name,
					'example_url': example_url,
					'app_type': app_type
				}
				examples.append(new_example)

########################################################################################################
########################################################################################################
applications = []
def got_applications():
	

	json_file = os.path.join(curdir, "data/application_info.json")
	with open(json_file, "r") as f:
		json_data = json.load(f)

	for id in range(0, len(json_data)):	
		count = 0		
		# Passing value into dict            
		app_type = json_data[id]["app_type"]
		app_rank = json_data[id]["mm_rank"]
		
		# Count number example of each application
		for exp in examples:
			if exp["app_type"] == str(app_type):
				count += 1

		new_app = {
			'type': app_type,
			'rank': app_rank,
			'no_examples': count,

		}
		applications.append(new_app)	

########################################################################################################
########################################################################################################
# Setup Jinja2
current_dir = os.path.dirname(os.path.abspath(__file__))
env = Environment(loader=FileSystemLoader(current_dir))
template = env.get_template('template/template.html')

# Render and save
got_repositories()
got_example_shield()
got_applications()

output = template.render(repositories=repositories, applications=applications, examples=examples)
with open(os.path.join(current_dir, 'index.html'), 'w', encoding='utf-8') as f:
	f.write(output)

print("HTML report generated successfully!")