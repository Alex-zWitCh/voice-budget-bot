# Changelog

All notable changes to SmartExpenseBot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-11-18

### Added

#### 🎯 Core Features
- **Income Tracking**: Added comprehensive income management feature
  - Support for monthly and daily income types
  - Text and voice input for income entries
  - Income confirmation workflow with AI extraction
  - Income included in financial reports and balance calculations

- **Account Management**:
  - **Delete Account** feature with confirmation dialog
  - Automatic cancellation of all scheduled reminders upon account deletion
  - Bot stops responding to deleted users (except `/start` command)
  - Complete data cascade deletion (expenses, incomes, reminders)

- **Currency Management**:
  - **Change Currency** option in settings menu
  - Currency selection prompt on first expense/income entry
  - Unified currency system - all expenses and incomes use user's currency from User table
  - Reports display all amounts in user's selected currency

#### 🌍 Localization & Internationalization
- **Multi-language Country Detection**: 
  - AI-powered country name detection in Uzbek, Russian, and English
  - Automatic timezone detection from country names in any language
  - Enhanced `deepseek_ai_country()` function for intelligent country recognition

- **Daily Expense Reminders**:
  - Automated daily reminders at 20:00 in user's local timezone
  - Reminders sent in user's preferred language
  - Automatic rescheduling when user changes timezone
  - Persistent reminders across bot restarts

#### 💰 Donation System
- **Telegram Stars Integration**:
  - Native Telegram Stars donation support
  - Preset donation amounts (10, 50, 100 stars)
  - Custom donation amount option
  - Automatic payment processing and thank you messages

- **Multiple Donation Platforms**:
  - Tirikchilik.uz integration for Uzbekistan users
  - Patreon monthly subscription support
  - GitHub Sponsors integration for developers
  - All donation options with multi-language support

#### 📊 Report Enhancements
- **Improved Report Generation**:
  - Reports now respond in user's selected language (Uzbek, Russian, English)
  - All markdown formatting removed for clean Telegram display
  - Income and expense balance calculations
  - Currency consistency - all amounts shown in user's currency
  - Enhanced AI prompts for better financial analysis

### Changed

#### 🔧 Technical Improvements
- **Voice Transcription Optimization**:
  - Implemented Singleton pattern for Vosk models
  - Models loaded only once, shared across all instances
  - Thread-safe model caching with double-check locking
  - Reduced memory usage and initialization time
  - Comprehensive logging for model loading and transcription

- **Database Schema**:
  - Income records now use currency from User table (not stored separately)
  - Expenses don't store currency (always use user's currency)
  - Improved data consistency across all financial records

- **Currency Handling**:
  - Unified currency system - single source of truth in User table
  - All financial operations use user's currency preference
  - Reports display everything in user's selected currency
  - Currency selection required on first expense/income entry

#### 🌐 User Experience
- **Language & Localization**:
  - All reports generated in user's language preference
  - Donation thank you messages in user's language
  - Enhanced multi-language support throughout the bot
  - Improved translation coverage

- **Report Display**:
  - Removed all markdown formatting (##, **, __, etc.)
  - Clean plain text output optimized for Telegram
  - Better formatting for financial summaries
  - Consistent currency display

### Fixed

#### 🐛 Bug Fixes
- **Report Generation**:
  - Fixed AttributeError when generating reports with income data
  - Income objects now properly handled in report context
  - Fixed currency mismatch in reports (now uses user's currency)

- **Account Deletion**:
  - Fixed bot continuing to respond after account deletion
  - Added user existence checks in all message handlers
  - Proper cleanup of scheduled reminders on deletion

- **Currency Issues**:
  - Fixed reports showing wrong currency (USD instead of user's choice)
  - Fixed income currency not matching user's preference
  - Ensured currency consistency across all features

- **Payment Processing**:
  - Fixed donation thank you messages always in English
  - Now uses user's language preference for thank you messages

- **Timezone Handling**:
  - Improved timezone detection from country names
  - Better fallback mechanisms for timezone identification
  - Fixed daily reminder scheduling with timezone changes

### Security

- **Data Protection**:
  - Secure account deletion with confirmation
  - Proper cascade deletion of all user data
  - Thread-safe database operations maintained

### Performance

- **Optimization**:
  - Reduced memory footprint with shared Vosk models
  - Faster voice transcription initialization
  - Improved database query efficiency
  - Better scheduler job management

### Documentation

- **Updated Requirements**:
  - Cleaned up `requirements.txt` with proper formatting
  - Added version specifications for all dependencies
  - Organized dependencies by category

---

## [1.1.0] - Previous Version

### Features
- Basic expense tracking
- Voice message transcription
- Multi-language support (English, Russian, Uzbek)
- Financial reports
- Reminder system
- Settings management

---

## Version History

- **v1.2.0** (2025-11-18): Major feature release with income tracking, account management, enhanced donations, and improved currency handling
- **v1.1.0**: Initial stable release with core expense tracking features
- **v1.0.0**: Initial release

---

## Upgrade Notes

### From v1.1.0 to v1.2.0

1. **Database Migration**: 
   - No manual migration required
   - Income table currency column will be populated from User table automatically
   - Existing expenses will use user's currency from User table for display

2. **New Dependencies**:
   - No new dependencies added
   - All existing dependencies remain the same

3. **Configuration**:
   - No configuration changes required
   - Existing `.env` file works as-is

4. **Breaking Changes**:
   - None - fully backward compatible

---

## Contributors

- Botir Bakhtiyarov - Project Maintainer

---

## Links

- [GitHub Repository](https://github.com/botirbakhtiyarov/SmartExpenseBot)
- [Patreon](https://www.patreon.com/15097645/join)
- [GitHub Sponsors](https://github.com/sponsors/botirbakhtiyarov)
- [Tirikchilik.uz](https://tirikchilik.uz/botir)

