import gitlab
import os
import sys
import json
import tempfile
import datetime
import requests
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

class GitLabScanner:

    def __init__(self, token: str, org_or_user: str, is_org: bool = True,
                output_dir: str = None, max_workers: int = 5):
        self.token = token
        self.org_or_user = org_or_user
        self.is_org = is_org
        self.output_dir = output_dir or os.path.join(os.getcwd(), "docker_analysis")
        self.headers = {
            "PRIVATE-TOKEN": self.token,
            "Accept": "application/json"
        }
        self.max_workers = max_workers
        self.scan_results = []
    
        os.makedirs(self.output_dir, exist_ok=True)
    
    def get_repositories(self) -> List[Dict[str, Any]]:
        """Download all repositories for org or user."""
        repos = []
        gl = gitlab.Gitlab("https://gitlab.com", private_token=self.token)
        
        try:
            # Authenticate first to catch auth issues early
            gl.auth()
            
            if self.is_org:
                # For a group (organization)
                print(f"Fetching repositories for group: {self.org_or_user}")
                try:
                    group = gl.groups.get(self.org_or_user)
                    projects = group.projects.list(all=True)
                    
                    for project in projects:
                        repos.append({
                            'id': project.id,
                            'name': project.name,
                            'description': project.description,
                            'web_url': project.web_url,
                            'visibility': project.visibility,
                            'default_branch': project.default_branch
                        })
                except gitlab.exceptions.GitlabGetError as e:
                    print(f"Error accessing group {self.org_or_user}: {e}")
                    return []
            else:
                # For a user
                print(f"Fetching repositories for user: {self.org_or_user}")
                try:
                    # Get current authenticated user
                    current_user = gl.user
                    
                    # If requested user is different than authenticated, warn
                    if current_user.username != self.org_or_user:
                        print(f"Warning: Cannot list projects for other users with this token.")
                        print(f"Showing projects for authenticated user '{current_user.username}' instead.")
                    
                    # List all projects owned by the user
                    projects = gl.projects.list(all=True, owned=True)
                    
                    for project in projects:
                        repos.append({
                            'id': project.id,
                            'name': project.name,
                            'description': project.description,
                            'web_url': project.web_url,
                            'visibility': project.visibility,
                            'default_branch': project.default_branch
                        })
                except gitlab.exceptions.GitlabError as e:
                    print(f"Error accessing user projects: {e}")
                    return []
        
        except gitlab.exceptions.GitlabAuthenticationError:
            print("Authentication failed. Please check your GitLab token.")
            return []
        
        print(f"Found {len(repos)} repositories for {self.org_or_user}")

        for repository in repos:
            print(f"  - {repository['name']}")

        return repos
    
    def search_dockerfiles(self, repo_name: str) -> List[Dict[str, str]]:
        """Search for Dockerfiles in a repository."""
        dockerfiles = []
        gl = gitlab.Gitlab("https://gitlab.com", private_token=self.token)
        
        # Find the project by name
        try:
            # Search for the project
            if self.is_org:
                group = gl.groups.get(self.org_or_user)
                projects = group.projects.list(all=True, search=repo_name)
                matching_projects = [p for p in projects if p.name == repo_name]
                if not matching_projects:
                    print(f"Could not find project: {repo_name}")
                    return []
                project = matching_projects[0]
            else:
                # Search in user's projects
                projects = gl.projects.list(all=True, owned=True, search=repo_name)
                matching_projects = [p for p in projects if p.name == repo_name]
                if not matching_projects:
                    print(f"Could not find project: {repo_name}")
                    return []
                project = matching_projects[0]
                
            # Try branches in order of priority
            branches = ['main', 'master']
            
            # Add default branch if it exists and is different
            if project.default_branch and project.default_branch not in branches:
                branches.insert(0, project.default_branch)
            
            for branch in branches:
                try:
                    # Check if branch exists
                    try:
                        project.branches.get(branch)
                    except gitlab.exceptions.GitlabGetError:
                        continue
                    
                    # Get repository tree (recursive) to find Dockerfiles
                    items = project.repository_tree(path='', ref=branch, recursive=True, all=True)
                    
                    for item in items:
                        if item['type'] == 'blob':  # File, not directory
                            path = item['path']
                            if path.endswith("Dockerfile") or path.endswith(".dockerfile") or "/Dockerfile." in path:
                                dockerfile = {
                                    'path': path,
                                    'repo': repo_name,
                                    'branch': branch,
                                    'download_url': f"{project.web_url}/-/raw/{branch}/{path}",
                                    'project_id': project.id
                                }
                                dockerfiles.append(dockerfile)
                    
                    # If we found Dockerfiles, no need to check other branches
                    if dockerfiles:
                        break
                        
                except gitlab.exceptions.GitlabError as e:
                    print(f"Error while searching Dockerfiles in {repo_name} on branch {branch}: {e}")
                    continue
                
        except gitlab.exceptions.GitlabError as e:
            print(f"Error accessing repository {repo_name}: {e}")
            
        return dockerfiles
    
    def download_dockerfile(self, dockerfile: Dict[str, str], temp_dir: str) -> Optional[str]:
        """Download Dockerfile from GitLab."""
        try:
            gl = gitlab.Gitlab("https://gitlab.com", private_token=self.token)
            project = gl.projects.get(dockerfile['project_id'])
            
            # Get the file content using GitLab API
            file_content = project.files.raw(
                file_path=dockerfile['path'],
                ref=dockerfile['branch']
            )
            
            local_path = os.path.join(temp_dir, "Dockerfile")
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, "wb") as f:
                f.write(file_content)
            
            return local_path
        except Exception as e:
            print(f"Error during downloading {dockerfile['path']}: {str(e)}")
            return None
    
    def scan_repository(self, repo_name: str, 
                        show_tags: bool = True,
                        private_registries: List[str] = None,
                        custom_rules: Dict[str, Any] = None,
                        threshold: int = 3,
                        force_level: Optional[int] = None,
                        output_format: str = 'json',
                        slack_webhook: Optional[str] = None,
                        ignore_patterns: List[str] = None,
                        no_info: bool = False) -> Dict[str, Any]:
        """Scan a GitLab repository for Docker images."""
        from docker.dockerfile_parser import extract_base_images
        from src.image_analyzer import analyze_image_tags
        from src.image_ignore import ImageIgnoreManager
        from utils.formatters import get_formatter
        from utils.slack_notifier import send_slack_notification
        
        start_time = time.time()
        
        dockerfiles = self.search_dockerfiles(repo_name)
        
        if not dockerfiles:
            return {
                "repository": repo_name,
                "status": "no Dockerfiles",
                "message": "Could not find any Dockerfiles",
                "duration_seconds": time.time() - start_time
            }
        
        ignore_manager = ImageIgnoreManager()
        if ignore_patterns:
            ignore_manager.add_patterns_from_list(ignore_patterns)
        
        all_results = []
        reports = []
        
        for dockerfile in dockerfiles:
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = self.download_dockerfile(dockerfile, temp_dir)
                
                if not local_path:
                    print(f"Could not download Dockerfile: {dockerfile['path']}")
                    continue
                
                if not no_info:
                    print(f"Analyzing {dockerfile['path']} in repository {repo_name}")
                
                try:
                    try:
                        image_info_list = extract_base_images(local_path)
                    except TypeError:
                        image_info_list = extract_base_images(local_path, no_info)
                except Exception as e:
                    print(f"Error extracting images from {dockerfile['path']}: {str(e)}")
                    continue
                
                if not image_info_list:
                    print(f"No Docker images found in: {dockerfile['path']}")
                    continue
                
                # Filter images based on ignore patterns
                filtered_image_info_list = []
                ignored_images = []
                
                for info in image_info_list:
                    if ignore_manager.should_ignore(info['image']):
                        ignored_images.append(info['image'])
                    else:
                        filtered_image_info_list.append(info)
                
                if ignored_images and not no_info:
                    print(f"Ignoring {len(ignored_images)} image(s) in {dockerfile['path']}:")
                    for img in ignored_images:
                        print(f"  - {img}")
                
                if not filtered_image_info_list:
                    print(f"All images are being ignored in {dockerfile['path']}. Nothing to analyze.")
                    continue
                
                image_info_list = filtered_image_info_list
                total_images = len(image_info_list)
                
                dockerfile_results = []
                outdated_images = []
                warning_images = []
                unknown_images = []
                
                for i, info in enumerate(image_info_list, 1):
                    try:
                        try:
                            result = analyze_image_tags(
                                info['image'], 
                                i, 
                                total_images, 
                                threshold, 
                                force_level,
                                private_registries,
                                custom_rules,
                                no_info
                            )
                        except TypeError:
                            result = analyze_image_tags(
                                info['image'], 
                                i, 
                                total_images, 
                                threshold, 
                                force_level,
                                private_registries,
                                custom_rules
                            )
                        
                        result['repository'] = repo_name
                        
                        dockerfile_results.append(result)
                        
                        if result['status'] == 'OUTDATED':
                            outdated_images.append(result)
                        elif result['status'] == 'WARNING':
                            warning_images.append(result)
                        elif result['status'] == 'UNKNOWN':
                            unknown_images.append(result)
                    except Exception as e:
                        print(f"Error during the analysis {info['image']}: {str(e)}")
                        dockerfile_results.append({
                            'image': info['image'],
                            'repository': repo_name,
                            'status': 'ERROR',
                            'message': f"Error: {str(e)}"
                        })
                
                if ignored_images:
                    dockerfile_results.append({
                        'image': 'IGNORED_IMAGES_SUMMARY',
                        'repository': repo_name,
                        'status': 'INFO',
                        'message': f"{len(ignored_images)} images have been ignored",
                        'ignored_images': ignored_images
                    })
                
                formatter = get_formatter(output_format, include_timestamp=True)
                
                gitlab_info = {
                    'org_or_user': self.org_or_user,
                    'repo': repo_name,
                    'path': dockerfile['path'],
                    'url': f"{dockerfile['download_url'].replace('/-/raw/', '/-/blob/')}"
                }
                
                formatted_output = formatter.format(
                    dockerfile_results, 
                    total_images, 
                    len(image_info_list) + len(ignored_images),
                    github_info=gitlab_info
                )
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                report_filename = f"{repo_name}_{dockerfile['path'].replace('/', '_')}_{timestamp}.{output_format}"
                report_path = os.path.join(self.output_dir, report_filename)
                
                formatter.save_to_file(formatted_output, report_path)
                
                if slack_webhook and (outdated_images or warning_images):
                    additional_info = {
                        'Repository': repo_name,
                        'Dockerfile': dockerfile['path'],
                        'GitLab URL': gitlab_info['url']
                    }
                    
                    send_slack_notification(
                        dockerfile_results,
                        f"{repo_name}/{dockerfile['path']}",
                        webhook_url=slack_webhook,
                        additional_info=additional_info
                    )
                
                all_results.extend(dockerfile_results)
                reports.append({
                    'dockerfile': dockerfile,
                    'report_path': report_path,
                    'total_images': total_images,
                    'outdated': len(outdated_images),
                    'warnings': len(warning_images),
                    'unknown': len(unknown_images),
                    'results': dockerfile_results
                })
        
        result = {
            "repository": repo_name,
            "status": "success",
            "message": f"Analyzed {len(dockerfiles)} Dockerfile(s)",
            "dockerfiles": dockerfiles,
            "reports": reports,
            "results": all_results,
            "duration_seconds": time.time() - start_time
        }
        
        for res in all_results:
            if 'repository' not in res:
                res['repository'] = repo_name
        
        self.scan_results.append(result)
        return result
    
    def scan_repositories(self, show_tags: bool = True,
                         private_registries: List[str] = None,
                         custom_rules: Dict[str, Any] = None,
                         threshold: int = 3,
                         force_level: Optional[int] = None,
                         output_format: str = 'json',
                         slack_webhook: Optional[str] = None,
                         ignore_patterns: List[str] = None,
                         no_info: bool = False) -> Dict[str, Any]:
        """Scan all GitLab repositories for Docker images."""
        start_time = time.time()
        repos = self.get_repositories()
        
        if not repos:
            print(f"Could not find any repositories for: {self.org_or_user}")
            return {
                "org_or_user": self.org_or_user,
                "status": "no_repositories",
                "message": "Could not find any repositories",
                "duration_seconds": time.time() - start_time
            }
        
        print(f"\nScanning {len(repos)} repositories...")
        
        self.scan_results = []
        
        # Parallel scanning of repositories
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for repo in repos:
                future = executor.submit(
                    self.scan_repository,
                    repo["name"],
                    show_tags,
                    private_registries,
                    custom_rules,
                    threshold,
                    force_level,
                    output_format,
                    slack_webhook,
                    ignore_patterns,
                    no_info
                )
                futures[future] = repo["name"]
            
            for i, future in enumerate(as_completed(futures), 1):
                try:
                    repo_name = futures[future]
                    result = future.result()
                    status = result.get("status", "unknown")
                    print(f"[{i}/{len(repos)}] Scanned {repo_name} - {status}")
                except Exception as e:
                    repo_name = futures[future]
                    print(f"Error during scanning {repo_name}: {str(e)}")
        
        # Generate summary report
        self.generate_summary_report(output_format)
        
        # Prepare final report
        entity_type = "group" if self.is_org else "user"
        scan_report = {
            "scan_date": datetime.datetime.now().isoformat(),
            "org_or_user": self.org_or_user,
            "total_repos": len(repos),
            "repos_with_dockerfiles": len([r for r in self.scan_results if r.get("status") == "success"]),
            "duration_seconds": time.time() - start_time,
            "results": self.scan_results
        }
        
        # Save full JSON report
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"gitlab_scan_{self.org_or_user}_{timestamp}.json"
        report_path = os.path.join(self.output_dir, report_filename)
        
        with open(report_path, "w") as f:
            json.dump(scan_report, f, indent=2)
        
        print(f"Full report saved to: {report_path}")
        return scan_report
    
    def generate_summary_report(self, output_format: str = 'html') -> str:
        """Generate a summary report of all scanned repositories."""
        from utils.formatters import get_formatter
        
        # Collect all results from repositories
        all_results = []
        for repo_result in self.scan_results:
            if 'results' in repo_result:
                # Add results from this repository to the overall list
                for result in repo_result.get('results', []):
                    # Ensure each result has repository information
                    if 'repository' not in result:
                        result['repository'] = repo_result.get('repository', 'Unknown')
                    all_results.append(result)
        
        # Create formatter and generate report
        formatter = get_formatter(output_format, include_timestamp=True)
        total_images = len(all_results)
        
        # Add information about GitLab organization/user
        gitlab_info = {
            'org_or_user': self.org_or_user,
            'type': 'Group' if self.is_org else 'User',
            'url': f"https://gitlab.com/{self.org_or_user}",
            'is_summary': True  # Indicates this is a summary report
        }
        
        formatted_output = formatter.format(all_results, total_images, github_info=gitlab_info)
        
        # Save report
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"gitlab_summary_{self.org_or_user}_{timestamp}.{output_format}"
        report_path = os.path.join(self.output_dir, report_filename)
        
        formatter.save_to_file(formatted_output, report_path)
        print(f"Summary report saved to: {report_path}")
        
        return report_path


def gitlab_scan(args):
    """Function to run GitLab scanning from command line arguments."""
    from utils.utils import parse_private_registries, load_custom_rules
    from src.image_ignore import parse_ignore_options
    
    # Variables for GitLab Scanner
    token = None
    org   = None
    user  = None
    
    if '--gitlab-token' in args:
        try:
            idx = args.index('--gitlab-token')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                token = args[idx + 1]
        except (ValueError, IndexError):
            pass
    
    if not token:
        token = os.environ.get('GITLAB_TOKEN')
    
    if not token:
        print("Error: You do not provide the token. Please use --gitlab-token TOKEN or set env variable GITLAB_TOKEN.")
        sys.exit(1)

    if '--gitlab-org' in args:
        try:
            idx = args.index('--gitlab-org')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                org = args[idx + 1]
        except (ValueError, IndexError):
            pass
    
    if '--gitlab-user' in args:
        try:
            idx = args.index('--gitlab-user')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                user = args[idx + 1]
        except (ValueError, IndexError):
            pass
    
    if not org and not user:
        print("Error: You do not provide the org neither user GitLab. Use --gitlab-org ORG or --gitlab-user USER.")
        sys.exit(1)
    
    output_dir = None
    if '--output-dir' in args:
        try:
            idx = args.index('--output-dir')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                output_dir = args[idx + 1]
        except (ValueError, IndexError):
            pass

    no_info = '--no-info' in args
    
    max_workers = 5
    if '--max-workers' in args:
        try:
            idx = args.index('--max-workers')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                max_workers = int(args[idx + 1])
        except (ValueError, IndexError):
            pass
    
    if org:
        scanner = GitLabScanner(token, org, is_org=True, output_dir=output_dir, max_workers=max_workers)
    else:
        scanner = GitLabScanner(token, user, is_org=False, output_dir=output_dir, max_workers=max_workers)
    
    show_tags = "--tags" in args
    
    private_registries = parse_private_registries(args)
    
    custom_rules = {}
    if "--rules" in args:
        try:
            idx = args.index("--rules")
            if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                rules_file = args[idx + 1]
                custom_rules = load_custom_rules(rules_file)
        except ValueError:
            pass
    
    ignore_manager = parse_ignore_options(args)
    ignore_patterns = ignore_manager.get_patterns()
    
    threshold = 3
    for i, arg in enumerate(args):
        if arg == "--threshold" and i + 1 < len(args):
            try:
                threshold = int(args[i + 1])
            except ValueError:
                pass
    
    force_level = None
    for i, arg in enumerate(args):
        if arg == "--level" and i + 1 < len(args):
            try:
                level = int(args[i + 1])
                if 1 <= level <= 3:
                    force_level = level
            except ValueError:
                pass

    output_format = 'html' 
    if '--output' in args:
        try:
            idx = args.index('--output')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                output_format = args[idx + 1].lower()
        except (ValueError, IndexError):
            pass
    
    slack_webhook = None
    if '--slack-webhook' in args:
        try:
            idx = args.index('--slack-webhook')
            if idx + 1 < len(args) and not args[idx + 1].startswith('--'):
                slack_webhook = args[idx + 1]
        except (ValueError, IndexError):
            pass
    
    if not slack_webhook and '--slack-notify' in args:
        slack_webhook = os.environ.get('SLACK_WEBHOOK_URL')
    
    scanner.scan_repositories(
        show_tags=show_tags,
        private_registries=private_registries,
        custom_rules=custom_rules,
        threshold=threshold,
        force_level=force_level,
        output_format=output_format,
        slack_webhook=slack_webhook,
        ignore_patterns=ignore_patterns,
        no_info=no_info
    )