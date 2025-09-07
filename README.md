# Rosenberg

## Get a Temporary OAuth 2.0 Token

1. Go to the Google OAuth 2.0 Playground:  
   https://developers.google.com/oauthplayground
2. In the "Select & authorize APIs" section on the left, find **"Drive API v3"**.
3. Expand it and select the scope:  
   https://www.googleapis.com/auth/drive.readonly  
   This gives temporary, read-only access to your files.
4. Click the blue **"Authorize APIs"** button.
5. A Google login window will appear. Choose your account and grant permission.
6. You will be redirected back to the playground. Click the **"Exchange authorization code for tokens"** button.
7. The panel on the right will now be populated. Copy the value from the **"Access token"** field. It will be a long string starting with ya29.a0.... This is your temporary token.
8. Save this token to a file, e.g., `token.txt`.
9. Export the token as an environment variable:
```shell
export GOOGLE_OAUTH_TOKEN="$(cat token.txt)"
```

## Run the Script

```shell
chmod +x download_doc.sh
chmod +x clean_markdown.sh 
./download_doc.sh https://docs.google.com/document/d/1BAfsC2IshoZsX5ulN1dW2ywa9ePYn45DmyGQeAanw10 $GOOGLE_OAUTH_TOKEN rosenberg.md
./clean_markdown.sh rosenberg.md
```