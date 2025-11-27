<div align="center">

<img src="arccompanion.png" alt="Arc Companion Logo" width="200"/>

# 🎮 Arc Companion

> **Note:** This project is coded with the help of AI, demonstrating the power of AI-assisted development.

### Your Ultimate In-Game Companion for Arc Raiders

[🌐 Visit Website](https://www.arc-companion.xyz)


[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/Joopz0r/ArcCompanion-public/releases)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-yellow.svg)](https://www.python.org/)

**Arc Companion** is a powerful, lightning-fast desktop application designed to enhance your Arc Raiders gameplay experience. Access real-time item information, track quests and hideout progression, and manage your in-game goals—all through customizable overlays and an intuitive progress hub.

[📥 Download Latest Release](https://github.com/Joopz0r/ArcCompanion-public/releases) • [📖 Documentation](#-features) • [🐛 Report Bug](https://github.com/Joopz0r/ArcCompanion-public/issues) • [💡 Request Feature](https://github.com/Joopz0r/ArcCompanion-public/issues) • [🐛 Report Item/Data Issues](https://github.com/Joopz0r/arcraiders-data).

</div>

---

## ✨ Features

### 🔍 **Instant Item Information**
Press a customizable hotkey while hovering over any item in-game to instantly display:
- 💰 **Market Value & Rarity**
- 🛠️ **Crafting Recipes & Requirements**
- 🏪 **Trader Availability**
- 🏠 **Hideout & Project Requirements**

### 📋 **Quest Tracking Overlay**
- Display only the quests **you** choose to track
- Compact, non-intrusive on-screen overlay
- Toggle visibility with a hotkey
- Check off individual objectives as you complete them

### 🎯 **Unified Progress Hub**
A powerful tabbed interface to manage all your in-game progression:

#### **Quest Manager**
- ✅ Track and filter active quests
- 🎯 Check off individual objectives
- ↕️ Reorder quests
- 🔍 Show/hide completed quests

#### **Hideout Tracker**
- 🏗️ Monitor all station upgrade levels
- 📊 Visual progress bars for material requirements
- 🎨 Color-coded completion indicators
- 🔄 Reorder and organize stations

#### **Expedition Project**
- 🚀 Track phase-by-phase material contributions
- ✨ Clear visibility of project milestones
- 📈 Progress visualization

### 📚 **Item Database Browser**
- 🔎 Browse and search through all Arc Raiders items
- 📊 View detailed item statistics and information
- ✅ Mark items as "tracked" to highlight them in overlays
- ✅ Add notes to items as to display them in overlays
- 🖼️ View item icons and images
- 🔗 Quick access to all item data in one place

### 🔄 **Automatic Data Updates**
- 📡 Connect to the community repository for latest data
- ⚡ No need to redownload the entire application
- 🗄️ Keep item prices, recipes, and game data fresh

### 💾 **Smart Auto-Save**
- ⏱️ All changes saved automatically after a few seconds
- 🔒 Never lose your progress
- 🚀 Seamless background operation

### 🖥️ **System Tray Integration**
- 👁️ Runs silently in the background
- 🖱️ Quick access via right-click menu
- ⚙️ Instant access to Settings and Progress Hub

---

## 📦 Installation

### Quick Start

1. **📥 Download**
   - Download the latest `Arc Companion` from the [Releases](https://www.arc-companion.xyz/) page

2. **📂 Extract**
   - Install the contents to a **permanent location** (e.g., `C:\Program Files\Arc Companion`)
   - ⚠️ **IMPORTANT**: Do not run directly from the Downloads folder

3. **🖱️ Create Desktop Shortcut**
   - Right-click `ArcCompanion.exe` → **Create shortcut**
   - Move the shortcut to your Desktop for easy access

4. **🚀 Launch**
   - Double-click the shortcut
   - The Arc Companion icon will appear in your **system tray** (near the clock)

---

## 🎮 Usage Guide

### First Time Setup

1. **🔧 Configure Settings**
   - Right-click the system tray icon
   - Select **Settings**
   - Configure your preferred hotkeys (default: `Ctrl+F` for items, `Ctrl+E` for quests)
   
2. **📡 Update Game Data**
   - In the Settings window, click **Check for Updates**
   - Download the latest item database and prices

### Daily Use

#### 🔍 Check Item Information
1. Hover your mouse over any item in Arc Raiders
2. Press your configured hotkey (default: **Ctrl+F**)
3. View the instant overlay with all item details

#### 📋 View Tracked Quests
1. Press your quest log hotkey (default: **Ctrl+E**)
2. See your custom-tracked quests on screen

#### 📊 Manage Progress
1. Right-click the tray icon → **Progress Hub**
2. Use the tabs to navigate:
   - **Quests**: Track and manage quest objectives
   - **Hideout**: Monitor station upgrades and materials
   - **Expeditions**: Track project contributions
3. All changes auto-save when you close or switch windows

#### 🚪 Exit Application
- Right-click the tray icon → **Exit**

---

## ⚙️ System Requirements

| Component | Requirement |
|-----------|------------|
| **OS** | Windows 10/11 (64-bit) |
| **RAM** | 4 GB minimum |
| **Storage** | 500 MB available space |
| **Display** | 1920x1080 or higher recommended |
| **Permissions** | Administrator rights (for global hotkeys) |

---

## 🛠️ Troubleshooting

### Application Closes Immediately
**Problem**: The program exits right after launch.

**Solution**:
- ✅ Verify `data` folder exists with all required files
- ✅ Do not run from a temporary location (Downloads folder, inside .zip)

### Hotkeys Don't Work
**Problem**: Pressing configured hotkeys doesn't trigger overlays.

**Solution**:
- ✅ Run application as **Administrator**
  - Right-click shortcut → **Properties** → **Compatibility** → Check "Run as Administrator"
- ✅ Ensure Arc Raiders is running in **Windowed** or **Borderless** mode
- ✅ Check for hotkey conflicts with other applications

### Antivirus False Positive
**Problem**: Antivirus software flags `ArcCompanion.exe` as suspicious.

**Solution**:
- ✅ This is common for PyInstaller-compiled executables
- ✅ Add an exception/exclusion for `ArcCompanion.exe` in your antivirus
- ✅ The application is safe to use

### OCR Not Recognizing Items
**Problem**: Item overlay doesn't appear or shows wrong items.

**Solution**:
- ✅ Ensure game is running at **100% UI scale**
- ✅ Check that tooltip color matches default (adjust in Settings config.ini if needed)
      [OCR]
      target_color = 249, 238, 223 (default setting)
- ✅ Try re-scanning the item with better cursor positioning

### Data Updates Fail
**Problem**: "Check for Updates" button doesn't download new data.

**Solution**:
- ✅ Check your internet connection
- ✅ Ensure firewall isn't blocking the application
- ✅ Try running as Administrator

---

## 🏗️ Building from Source

Want to contribute or build your own version?

```bash
# Clone the repository
git clone https://github.com/Joopz0r/ArcCompanion-public.git
cd ArcCompanion-public

# Install dependencies
pip install -r requirements.txt

# Run the application (for testing/development)
python arc_companion.py

# Build executable
# First, install PyInstaller if you haven't already
pip install pyinstaller

# Build using the spec file (includes icon, Tesseract-OCR, runs without console window)
pyinstaller ArcCompanion.spec

# The built application will be in: dist/ArcCompanion/
```

### 📦 Dependencies
- `PyQt6` - GUI framework
- `Pillow` - Image processing
- `pytesseract` - OCR engine
- `rapidfuzz` - Fuzzy string matching
- `pyperclip` - Clipboard operations
- `pynput` - Global hotkey detection
- `pystray` - System tray integration

### 🏗️ Build Notes
- The executable is configured to run **without a console window** (system tray only)
- **Tesseract-OCR** is bundled with the executable for portability
- The **data folder** is kept separate to allow for easy updates without rebuilding

---

## 🤝 Contributing

Contributions are welcome! Whether it's bug reports, feature requests, or code contributions:

1. 🍴 Fork the repository
2. 🌿 Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. 💾 Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. 📤 Push to the branch (`git push origin feature/AmazingFeature`)
5. 🔀 Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Arc Raiders** - by [Embark Studios](https://www.embark-studios.com/)
- **[RaidTheory/arcraiders-data](https://github.com/RaidTheory/arcraiders-data)** - for the comprehensive game data repository that powers this application
- **Tesseract OCR** - for optical character recognition capabilities
- All the players who provided feedback and bug reports during development

---

## 📞 Support & Community

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/Joopz0r/ArcCompanion-public/issues)
- 💡 **Feature Requests**: [GitHub Issues](https://github.com/Joopz0r/ArcCompanion-public/issues)
- 💬 **Discord**: [Join our Community](https://discord.gg/RzjPhXCXfH)
- 📧 **Contact**: Open an issue on GitHub

---

<div align="center">

**Made with ❤️ for the Arc Raiders community**

⭐ **Star this project if you find it useful!** ⭐

[⬆ Back to Top](#-arc-companion)

</div>
