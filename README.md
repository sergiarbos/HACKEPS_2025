LA Neighborhood Recommender - "The Iron Map"

This web application recommends the top 5 neighborhoods in Los Angeles based on personal preferences. Wrapped in a "Game of Thrones" theme, the tool balances complex data analysis with an engaging user experience.
🚀 How It Works

The user journey follows a four-step process:

    Entry Gate: A thematic landing screen inspired by the Seven Kingdoms.

    Profile Selection: Users can choose their path:

        Avatar: Select a predefined profile with preset preferences.

        Custom Form: Fill out a detailed questionnaire covering demographics, lifestyle, mobility, and priorities.

    The Scoring Engine: The app processes these responses to calculate a unique score for every neighborhood in the database.

    The Small Council Report: The results display the Top 5 recommendations, featuring:

        Key Metrics: Safety, Income, Noise, Leisure, and Mobility.

        Mapping: An interactive map for each recommended area.

📊 Data Pipeline & Backend

Behind the scenes, the project includes a robust ETL (Extract, Transform, Load) process to build the core dataset:

    Data Sourcing: Neighborhood boundaries and features are collected from OpenStreetMap (OSM).

    Metric Integration: The scripts aggregate data regarding:

        Demographics and average income.

        Crime rates and safety indices.

        Noise pollution and proximity to parks/green spaces.

        Essential services and public transportation networks.

    Final Consolidation: All variables are normalized and combined into a final CSV file used by the recommender algorithm.

🛠️ Tech Stack

    Logic & Analysis: Python (Pandas for data wrangling).

    Geospatial Data: OpenStreetMap API.

    Web Framework: [Insert Framework, e.g., Streamlit / Flask / React].


Installation & Usage

    Clone the repository.

    Install dependencies: pip install -r requirements.txt.

    (Optional) Run the data scripts in /scripts to rebuild the CSV.

    Launch the app: [Insert your launch command here, e.g., streamlit run app.py]
