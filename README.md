<div align="center">

```
██╗    ██╗██╗  ██╗███████╗███████╗██╗     ██╗   ██╗███████╗██████╗ ███████╗███████╗
██║    ██║██║  ██║██╔════╝██╔════╝██║     ██║   ██║██╔════╝██╔══██╗██╔════╝██╔════╝
██║ █╗ ██║███████║█████╗  █████╗  ██║     ██║   ██║█████╗  ██████╔╝███████╗█████╗  
██║███╗██║██╔══██║██╔══╝  ██╔══╝  ██║     ╚██╗ ██╔╝██╔══╝  ██╔══██╗╚════██║██╔══╝  
╚███╔███╔╝██║  ██║███████╗███████╗███████╗ ╚████╔╝ ███████╗██║  ██║███████║███████╗
 ╚══╝╚══╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝
```

**Enter the Universe of Wheels**

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.x-092E20?style=flat-square&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![License](https://img.shields.io/badge/License-MIT-f2ca50?style=flat-square)](LICENSE)

*A premium e-commerce platform for die-cast car collectors*

[Features](#-key-features) · [Tech Stack](#-tech-stack) · [Getting Started](#-getting-started) · [Project Structure](#-project-structure) · [Screenshots](#-screenshots)

</div>

---

## 📖 Overview

WheelVerse is a full-featured, premium e-commerce web application built for die-cast model car enthusiasts. It delivers a modern, secure shopping experience complete with OTP-based authentication, product variant management, a wallet system, order tracking, and a powerful admin dashboard — all wrapped in a sleek dark UI inspired by the aesthetics of high-performance automotive culture.

---

## ✨ Key Features

### 🔐 Authentication & Security
- Email OTP verification for signup and password reset
- Secure session-based login with Django authentication
- Change-email flow with OTP confirmation to current address
- CSRF protection, password hashing, and server-side input validation
- Google OAuth login *(planned)*

### 🚗 Product Management
- Product categories with soft-delete support
- Multiple product variants (scale, color, edition)
- Multiple images per variant with Cropper.js integration
- Rarity tagging and inventory tracking
- Search, filter, and sort on the collections page

### 🛒 Shopping Experience
- Add to cart, update quantities, remove items
- Wishlist with move-to-cart functionality
- Cart summary with shipping calculation

### 📦 Orders & Wallet
- Place orders, view order history and status
- Cancel and return order flows
- Wallet balance, wallet-funded purchases, and refund management

### 👤 User Profile
- Edit profile with image upload and crop
- Address book with default address management
- Change password and change email from profile

### 🛠 Admin Dashboard
- Manage users, categories, products, and variants
- Order management with status updates
- Offer and inventory management
- Soft-delete across all major entities

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3, Django 6.x |
| **Database** | PostgreSQL |
| **Frontend** | HTML5, CSS3, Tailwind CSS, JavaScript |
| **Fonts** | Orbitron, Poppins (Google Fonts) |
| **Image Handling** | Cropper.js |
| **Email** | Django `send_mail` via Gmail SMTP |
| **Version Control** | Git, GitHub |
| **Dev Tools** | VS Code, Postman, pgAdmin |

---

## 💻 System Requirements

**Minimum**
- Intel Core i3 · 4 GB RAM · 20 GB Storage

**Recommended**
- Intel Core i5/i7 · 8 GB RAM · SSD Storage · Windows 10/11

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/wheelverse.git
cd wheelverse
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-django-secret-key

DEBUG=True

# PostgreSQL
DB_NAME=wheelverse_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Gmail SMTP
EMAIL_HOST_USER=your_gmail@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=your_gmail@gmail.com
```

> **Gmail setup:** Enable 2FA on your Google account, then generate an App Password under *Security → App Passwords* and use it as `EMAIL_HOST_PASSWORD`.

### 5. Create the PostgreSQL database

```sql
CREATE DATABASE wheelverse_db;
```

### 6. Apply migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create a superuser

```bash
python manage.py createsuperuser
```

### 8. Run the development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

---

## 🗂 Project Structure

```
wheelverse/
│
├── accounts/                   # Auth, profile, address management
│   ├── templates/
│   │   ├── accounts/           # Signup, login, OTP, reset pages
│   │   ├── address/            # Address CRUD pages
│   │   └── emails/             # HTML email templates (OTP emails)
│   ├── models.py
│   ├── views.py
│   └── urls.py
│
├── adminpanel/                 # Admin dashboard app
│   ├── templates/adminpanel/
│   ├── models.py               # Product, Category, ProductVariant
│   ├── views.py
│   └── urls.py
│
├── Products/                   # Cart, Wishlist
│   ├── templates/products/
│   ├── models.py               # Cart, Wishlist
│   ├── views.py
│   └── urls.py
│
├── orders/                     # Order management
├── wallet/                     # Wallet & transactions
│
├── static/                     # Static assets (CSS, JS, images)
├── media/                      # User-uploaded files
│
├── wheelverse/                 # Project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── requirements.txt
├── manage.py
└── README.md
```

---

## 🔑 Authentication Flow

```
User Signup
    └── OTP sent to email
        └── Verify OTP → Account Activated → Login

Forgot Password
    └── Enter email → OTP sent
        └── Verify OTP → Reset Password → Login

Change Email (from profile)
    └── Enter new email → OTP sent to current email
        └── Verify OTP → Email Updated
```

---

## 🗄 Database Schema (Core Tables)

| Table | Description |
|---|---|
| `Users` | Custom user model with phone and profile picture |
| `Categories` | Product categories with soft delete |
| `Products` | Products with rarity, category, and active status |
| `ProductVariants` | Scale, color, stock, and price per variant |
| `VariantImages` | Multiple images per variant |
| `Cart` | User cart items linked to variants |
| `Wishlist` | Saved products per user |
| `Addresses` | User address book with default flag |
| `Orders` | Order header with status and total |
| `OrderItems` | Line items per order |
| `Wallet` | User wallet with balance |
| `WalletTransactions` | Debit/credit transaction log |

---

## 🛣 URL Routes (Summary)

| URL | View | Description |
|---|---|---|
| `/` | `landing_page` | Home / landing page |
| `/signup/` | `signup_view` | New user registration |
| `/signup/verify/` | `signup_verify_view` | OTP verification after signup |
| `/login/` | `login_view` | User login |
| `/logout/` | `logout_view` | User logout |
| `/forgot-password/` | `forgot_password_view` | Request password reset |
| `/verify-otp/` | `verify_otp_view` | Verify reset OTP |
| `/reset-password/` | `reset_password_view` | Set new password |
| `/profile/` | `profile_view` | User profile |
| `/profile/edit/` | `edit_profile_view` | Edit profile details |
| `/profile/change-email/` | `change_email_view` | Request email change |
| `/profile/change-email/verify/` | `change_email_otp_view` | Verify email change OTP |
| `/collections/` | `user_collections` | Browse all products |
| `/collections/<id>/` | `product_detail` | Single product detail |
| `/cart/` | `cart_view` | Shopping cart |
| `/wishlist/` | `wishlist_view` | Wishlist |
| `/addresses/` | `address_list` | Address book |

---

## 🔮 Roadmap

- [ ] Razorpay payment gateway integration
- [ ] Coupon and discount code system
- [ ] Product reviews and ratings
- [ ] AI-powered product recommendations
- [ ] Sales analytics dashboard
- [ ] Push notifications
- [ ] Mobile application
- [ ] Multi-language support
- [ ] Live order tracking
- [ ] Chat support

---

## 🔒 Security Notes

- All forms are CSRF-protected via Django middleware
- Passwords are hashed using Django's PBKDF2 algorithm
- OTPs expire after 60 seconds (signup/reset) or 10 minutes (email change)
- Session data is used for OTP state — never exposed to the client
- Input is validated both client-side and server-side on all forms

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

Built with passion for automotive culture and precision engineering.

**WheelVerse** · *Enter the Universe of Wheels*

</div>
