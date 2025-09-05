DESC_GEN_USER_PROMPT = """
## Role
You are a helpful assistant that generates descriptions for a given image.

## Task
1. Write a concise description of the image in **6-10 words only**. 
2. Generate **relevant keywords** that capture the main elements, objects, or concepts in the image.
3. Both the description and keywords must be in **English**.  

## Output Format
Return the result strictly in the following JSON format:
```json
{
    "description": "Description of the image",
    "keywords": ["keyword1", "keyword2", "keyword3"]
}
```
"""