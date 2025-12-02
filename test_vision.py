import os
# Use the repository mock implementation to avoid external credentials during tests
from mock_vision import MockImageAnnotatorClient, Image

# Initialize mock Vision client
client = MockImageAnnotatorClient()

# Path to test image
image_path = "static/uploads/ids/sample_id.jpg"
if not os.path.exists(image_path):
    # If the sample image isn't present, skip the test by printing a notice
    print(f"Sample image not found, skipping vision test: {image_path}")
else:
    # Load image
    with open(image_path, "rb") as f:
        content = f.read()

    image = Image(content=content)

    # Run mock OCR
    response = client.text_detection(image=image)

    if response.error and getattr(response.error, 'message', None):
        print("Mock API Error:", response.error.message)
    else:
        texts = response.text_annotations
        if texts:
            print("Detected mock text:")
            print(texts[0].description.strip())
        else:
            print("No text detected by mock.")
