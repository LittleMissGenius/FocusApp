# Moving this project to a separate `RecipeApp` repository

This repo now includes a standalone template in `recipeapp_template/`. To create a separate sibling repository named `RecipeApp`, run:

```bash
python move_to_recipeapp.py
```

Or explicitly via the script path:

```bash
python scripts/move_to_recipeapp.py
```

If you are in a Bash environment, this wrapper also works:

```bash
bash scripts/move_to_recipeapp.sh
```

On Windows CMD, you can also run:

```bat
move_to_recipeapp.bat
```

The script will:
1. Copy only the standalone `recipeapp_template/` files into a sibling folder named `RecipeApp`.
2. Initialize a fresh Git repository in that `RecipeApp` folder.
3. Create an initial commit.

Afterward, open and run the new repository:

```bash
cd ../RecipeApp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then visit `http://127.0.0.1:5000/recipes` after login.

## Windows (PowerShell)

```powershell
python move_to_recipeapp.py
cd ..\\RecipeApp
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
