"""
Mock Google Vision API implementation for ID verification
"""

import random
import os
from collections import namedtuple

# Mock response objects to simulate Google Vision API responses
TextAnnotation = namedtuple('TextAnnotation', ['description'])
MockResponse = namedtuple('MockResponse', ['text_annotations', 'error'])

class MockVisionError:
    def __init__(self, message):
        self.message = message

class MockImageAnnotatorClient:
    def __init__(self, credentials=None):
        # No actual credentials needed for mock
        pass
    
    def text_detection(self, image=None):
        """
        Simulate text detection with mock responses based on filename patterns
        """
        # Simulate different responses based on filename
        if image and hasattr(image, 'content'):
            # For more realistic mocking, we could analyze the actual image content
            # For now, we'll use filename patterns
            pass
        
        # Randomly generate responses to simulate different scenarios
        if random.random() < 0.1:  # 10% chance of API error
            return MockResponse(
                text_annotations=[],
                error=MockVisionError("Mock API error: Service temporarily unavailable")
            )
        elif random.random() < 0.15:  # 15% chance of no text detected
            return MockResponse(
                text_annotations=[],
                error=None
            )
        else:
            # Generate mock text annotations
            mock_texts = [
                "National Identification Card",
                "Republic of Kenya",
                "ID Number: 12345678",
                "Name: John Doe",
                "Date of Birth: 01/01/1990",
                "Gender: Male",
                "National ID",
                "Identity Card",
                "Government of Kenya",
                "Official Document",
                "Passport",
                "Driver's License",
                "身份证",
                "Identification"
            ]
            
            # Select random texts
            num_texts = random.randint(3, 8)
            selected_texts = random.sample(mock_texts, min(num_texts, len(mock_texts)))
            
            # Create text annotations
            text_annotations = [TextAnnotation(description=text) for text in selected_texts]
            
            # Add a full text annotation as the first element (like Google Vision)
            full_text = " ".join(selected_texts)
            text_annotations.insert(0, TextAnnotation(description=full_text))
            
            return MockResponse(
                text_annotations=text_annotations,
                error=None
            )

# Mock service account credentials
class MockCredentials:
    @staticmethod
    def from_service_account_file(key_path):
        # Verify the file exists but don't actually load credentials
        if os.path.exists(key_path):
            return "mock_credentials"
        else:
            raise FileNotFoundError(f"Service account file not found: {key_path}")

# Mock vision module functions
def detect_text(image_path):
    """
    Mock function to detect text in an image
    Returns a tuple (success, message) like the original verify_id_document function
    """
    client = MockImageAnnotatorClient()
    
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        # Create a mock image object
        MockImage = namedtuple('Image', ['content'])
        image = MockImage(content=content)
        
        response = client.text_detection(image=image)
        
        if response.error and response.error.message:
            return False, f"Mock Vision API error: {response.error.message}"
        
        texts = [t.description for t in response.text_annotations]
        if not texts:
            return False, "No text detected in mock analysis."
        
        return True, f"Mock detected text: {' | '.join(texts[:5])}"
    except Exception as e:
        return False, f"Mock analysis failed: {str(e)}"

# Mock Image class to match google.cloud.vision.Image interface
class Image:
    def __init__(self, content=None):
        self.content = content

# Export the same interface as google.cloud.vision
ImageAnnotatorClient = MockImageAnnotatorClient