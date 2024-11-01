# Rank4AI

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Demo](https://img.shields.io/badge/demo-promptboostai.com-green.svg)](https://promptboostai.com)

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Introduction

**Rank4AI** is a cutting-edge application designed to enhance and streamline AI-driven ranking systems. Built with scalability and performance in mind, Rank4AI leverages the power of the latest AI models to deliver accurate and efficient ranking solutions tailored to your needs.

Visit our website: [promptboostai.com](https://promptboostai.com)

## Features

- **Advanced Ranking Algorithms:** Utilizes state-of-the-art AI models for precise ranking.
- **Scalable Architecture:** Built to handle large datasets and high traffic.
- **User-Friendly Interface:** Intuitive dashboard for easy management and monitoring.
- **Customizable Settings:** Tailor the ranking parameters to fit your specific requirements.
- **API Integration:** Seamlessly integrates with existing systems through robust APIs.

## Installation

### Prerequisites

- **Python 3.8+**
- **Git**
- **Heroku CLI** (for deployment)

### Steps

1. **Clone the Repository**

   ```bash
   git clone https://github.com/BenUsername/rank4ai.git
   cd rank4ai
   ```

2. **Create a Virtual Environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**

   Create a `.env` file in the root directory and add the necessary configurations:

   ```env
   SECRET_KEY=your_secret_key
   DATABASE_URL=your_database_url
   GPT_MODEL=gpt-4o-mini
   ```

## Usage

### Running Locally

1. **Activate Virtual Environment**

   ```bash
   source venv/bin/activate
   ```

2. **Start the Application**

   ```bash
   python app.py
   ```

   The application will be accessible at `http://localhost:5000`.

### Deployment on Heroku

1. **Login to Heroku**

   ```bash
   heroku login
   ```

2. **Create a New Heroku App**

   ```bash
   heroku create your-app-name
   ```

3. **Set Environment Variables**

   ```bash
   heroku config:set SECRET_KEY=your_secret_key
   heroku config:set DATABASE_URL=your_database_url
   heroku config:set GPT_MODEL=gpt-4o-mini
   ```

4. **Push to Heroku**

   ```bash
   git push heroku main
   ```

   Your application will be deployed and accessible via the Heroku URL provided.

## Configuration

Configure the application by modifying the `config.py` file. Key configurations include:

- **Database Settings:** Define your database connection parameters.
- **AI Model Settings:** Specify the GPT model (`gpt-4o-mini`) for API calls.
- **Deployment Settings:** Adjust settings related to deployment on Heroku.

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the Repository**
2. **Create a New Branch**

   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Commit Your Changes**

   ```bash
   git commit -m "Add your feature"
   ```

4. **Push to the Branch**

   ```bash
   git push origin feature/YourFeature
   ```

5. **Open a Pull Request**

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

For any inquiries or support, please contact:

- **Email:** eduar.varil@proton.me
- **Website:** [promptboostai.com](https://promptboostai.com)
