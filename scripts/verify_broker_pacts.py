#!/usr/bin/env python3
"""
Verify Pact contracts from the broker against the FastAPI provider.

This script fetches pacts from the Pact Broker and verifies them
against the running FastAPI application.
"""

import os
import sys
import json
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.contracts.test_pact_provider import PactProviderVerifier
from src.api.main import app


@dataclass
class PactContract:
    """Represents a Pact contract from the broker."""
    consumer: str
    provider: str
    version: str
    pact_url: str
    tags: List[str]


class PactBrokerClient:
    """Client for interacting with the Pact Broker."""
    
    def __init__(self, broker_url: str, username: str = None, password: str = None):
        self.broker_url = broker_url.rstrip('/')
        self.auth = (username, password) if username and password else None
        
    def get_latest_pacts(self, provider: str, consumer: str = None, tag: str = None) -> List[PactContract]:
        """Fetch latest pacts for a provider from the broker."""
        url = f"{self.broker_url}/pacts/provider/{provider}/latest"
        
        if consumer:
            url += f"/consumer/{consumer}"
        if tag:
            url += f"/tag/{tag}"
            
        response = requests.get(url, auth=self.auth)
        
        if response.status_code == 404:
            print(f"No pacts found for provider '{provider}'")
            return []
            
        response.raise_for_status()
        data = response.json()
        
        # Handle both single pact and list of pacts
        pacts_data = data if isinstance(data, list) else [data]
        
        pacts = []
        for pact_data in pacts_data:
            # Extract consumer info
            consumer_name = pact_data.get('consumer', {}).get('name', 'unknown')
            version = pact_data.get('consumerVersion', 'unknown')
            
            # Get the pact URL
            pact_url = None
            for link in pact_data.get('_links', {}).values():
                if isinstance(link, dict) and 'href' in link:
                    if 'pact' in link.get('name', '').lower() or 'pact' in link['href']:
                        pact_url = link['href']
                        break
            
            if not pact_url:
                # Fallback: construct URL
                pact_url = f"{self.broker_url}/pacts/provider/{provider}/consumer/{consumer_name}/version/{version}"
            
            pacts.append(PactContract(
                consumer=consumer_name,
                provider=provider,
                version=version,
                pact_url=pact_url,
                tags=pact_data.get('tags', [])
            ))
            
        return pacts
    
    def download_pact(self, pact: PactContract) -> Dict[str, Any]:
        """Download a pact contract from the broker."""
        response = requests.get(pact.pact_url, auth=self.auth)
        response.raise_for_status()
        return response.json()
    
    def publish_verification_results(self, pact: PactContract, success: bool, 
                                   provider_version: str, results: Dict[str, Any] = None):
        """Publish verification results back to the broker."""
        url = f"{self.broker_url}/pacts/provider/{pact.provider}/consumer/{pact.consumer}/pact-version/{pact.version}/verification-results"
        
        payload = {
            "success": success,
            "providerApplicationVersion": provider_version,
            "verifiedBy": {
                "implementation": "FastAPI",
                "version": "0.100.0"
            }
        }
        
        if results:
            payload["testResults"] = results
            
        response = requests.post(url, json=payload, auth=self.auth)
        response.raise_for_status()
        return response.json()


def verify_pacts_from_broker():
    """Main function to verify pacts from the broker."""
    
    # Get configuration from environment
    broker_url = os.getenv('PACT_BROKER_URL', 'http://localhost:9292')
    broker_username = os.getenv('PACT_BROKER_USERNAME')
    broker_password = os.getenv('PACT_BROKER_PASSWORD')
    provider_name = 'TradingBotAPI'
    provider_version = os.getenv('GIT_COMMIT', 'local')
    
    print(f"🔍 Fetching pacts from broker: {broker_url}")
    print(f"📦 Provider: {provider_name} (version: {provider_version})")
    
    # Initialize clients
    broker_client = PactBrokerClient(broker_url, broker_username, broker_password)
    verifier = PactProviderVerifier(app)
    
    # Get latest pacts
    pacts = broker_client.get_latest_pacts(provider_name)
    
    if not pacts:
        print("❌ No pacts found to verify")
        return 1
    
    print(f"📝 Found {len(pacts)} pact(s) to verify")
    
    all_success = True
    results_summary = []
    
    for pact in pacts:
        print(f"\n🔄 Verifying pact: {pact.consumer} -> {pact.provider} (v{pact.version})")
        
        try:
            # Download the pact
            pact_data = broker_client.download_pact(pact)
            
            # Save to temporary file for verification
            pact_file = f"/tmp/pact-{pact.consumer}-{pact.provider}.json"
            with open(pact_file, 'w') as f:
                json.dump(pact_data, f)
            
            # Verify each interaction
            interactions = pact_data.get('interactions', [])
            interaction_results = []
            
            for interaction in interactions:
                description = interaction.get('description', 'Unknown interaction')
                provider_state = interaction.get('providerState')
                
                print(f"  • Testing: {description}")
                
                # Setup provider state
                if provider_state:
                    state_handler = verifier.setup_provider_states().get(provider_state)
                    if state_handler:
                        state_handler()
                    else:
                        print(f"    ⚠️  Unknown provider state: {provider_state}")
                
                # Make the request
                request = interaction.get('request', {})
                response_spec = interaction.get('response', {})
                
                try:
                    # Construct and execute the request
                    method = request.get('method', 'GET')
                    path = request.get('path', '/')
                    headers = request.get('headers', {})
                    body = request.get('body')
                    
                    # Use the test client
                    client_method = getattr(verifier.client, method.lower())
                    
                    kwargs = {'headers': headers}
                    if body:
                        kwargs['json'] = body
                    
                    actual_response = client_method(path, **kwargs)
                    
                    # Verify the response
                    assert actual_response.status_code == response_spec.get('status'), \
                        f"Status mismatch: {actual_response.status_code} != {response_spec.get('status')}"
                    
                    # TODO: Add more detailed response body verification
                    # This would normally use Pact matchers
                    
                    interaction_results.append({
                        'description': description,
                        'success': True
                    })
                    print(f"    ✅ Passed")
                    
                except Exception as e:
                    interaction_results.append({
                        'description': description,
                        'success': False,
                        'error': str(e)
                    })
                    print(f"    ❌ Failed: {e}")
                    all_success = False
            
            # Publish results back to broker
            verification_success = all([r['success'] for r in interaction_results])
            
            try:
                broker_client.publish_verification_results(
                    pact,
                    success=verification_success,
                    provider_version=provider_version,
                    results={'interactions': interaction_results}
                )
                print(f"  📤 Results published to broker")
            except Exception as e:
                print(f"  ⚠️  Failed to publish results: {e}")
            
            results_summary.append({
                'consumer': pact.consumer,
                'success': verification_success,
                'interactions': len(interactions),
                'passed': sum(1 for r in interaction_results if r['success'])
            })
            
        except Exception as e:
            print(f"  ❌ Verification failed: {e}")
            all_success = False
            results_summary.append({
                'consumer': pact.consumer,
                'success': False,
                'error': str(e)
            })
    
    # Print summary
    print("\n" + "="*60)
    print("📊 VERIFICATION SUMMARY")
    print("="*60)
    
    for result in results_summary:
        status = "✅" if result.get('success') else "❌"
        consumer = result['consumer']
        
        if 'interactions' in result:
            passed = result['passed']
            total = result['interactions']
            print(f"{status} {consumer}: {passed}/{total} interactions passed")
        else:
            error = result.get('error', 'Unknown error')
            print(f"{status} {consumer}: {error}")
    
    print("="*60)
    
    if all_success:
        print("✅ All pacts verified successfully!")
        return 0
    else:
        print("❌ Some pacts failed verification")
        return 1


if __name__ == "__main__":
    sys.exit(verify_pacts_from_broker())