import hashlib
import random
import os
import requests
import json
import time
from typing import Dict, List, Optional
from omegaconf import DictConfig

class CodeforcesAPI:
    def __init__(self, cfg: DictConfig):
        self.api_key = cfg.codeforces.key
        self.api_secret = cfg.codeforces.secret
        self.base_url = cfg.api.base_url
        self.contest_cache = {}
        
    def _generate_api_sig(self, method_name: str, params: Dict) -> str:
        rand = str(random.randint(100000, 999999))
        params['time'] = str(int(time.time()))
        params['apiKey'] = self.api_key
        params['time'] = params['time']
        
        sorted_params = sorted(params.items())
        param_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # create signature string
        sig_string = f"{rand}/{method_name}?{param_string}#{self.api_secret}"
        sig = hashlib.sha512(sig_string.encode()).hexdigest()
        
        params['apiSig'] = f"{rand}{sig}"
        return params
    
    def get_user_submissions(self, handle: str) -> List[Dict]:
        method = 'user.status'
        params = {'handle': handle}
        
        # add api sig for authenticated req
        params = self._generate_api_sig(method, params)
        
        url = f"{self.base_url}/{method}"
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] == 'OK':
                return data['result']
            else:
                print(f"API error for user {handle}: {data.get('comment', 'Unknown error')}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"Request error for user {handle}: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON decode error for user {handle}: {e}")
            return []
    
    def get_contest_info(self, contest_id: int) -> Optional[Dict]:
        if contest_id in self.contest_cache:
            return self.contest_cache[contest_id]
            
        method = 'contest.standings'
        params = {
            'contestId': str(contest_id),
            'from': '1',
            'count': '1',
            'showUnofficial': 'false'
        }
        
        url = f"{self.base_url}/{method}"
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data['status'] == 'OK':
                contest_info = data['result']['contest']
                problems = data['result']['problems']
                
                self.contest_cache[contest_id] = {
                    'contest': contest_info,
                    'problems': {p['index']: p for p in problems}
                }
                return self.contest_cache[contest_id]
            else:
                print(f"API error for contest {contest_id}: {data.get('comment', 'Unknown error')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request error for contest {contest_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error for contest {contest_id}: {e}")
            return None
