#!/bin/bash

# VBridge Modernized - Installation Script
# Compatible with Python 3.8-3.12 and Node.js 18+

set -e  # Exit on any error

echo "🚀 VBridge Modernized Installation Script"
echo "=========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check Python version
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        print_success "Found Python $PYTHON_VERSION"
        
        # Check if Python version is >= 3.8
        if [[ "$(echo "$PYTHON_VERSION >= 3.8" | bc -l)" -eq 1 ]]; then
            print_success "Python version is compatible (>=3.8)"
        else
            print_error "Python 3.8+ is required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 is not installed. Please install Python 3.8+ first."
        exit 1
    fi
    
    # Check Node.js version
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
        print_success "Found Node.js v$NODE_VERSION"
        
        if [[ $NODE_VERSION -ge 18 ]]; then
            print_success "Node.js version is compatible (>=18)"
        else
            print_warning "Node.js 18+ is recommended. Found: v$NODE_VERSION"
            print_warning "Some features may not work properly."
        fi
    else
        print_error "Node.js is not installed. Please install Node.js 18+ first."
        exit 1
    fi
    
    # Check npm
    if command -v npm &> /dev/null; then
        NPM_VERSION=$(npm --version)
        print_success "Found npm v$NPM_VERSION"
    else
        print_error "npm is not installed. Please install npm first."
        exit 1
    fi
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Check if we're in a virtual environment
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        print_success "Virtual environment detected: $VIRTUAL_ENV"
    else
        print_warning "No virtual environment detected."
        print_warning "It's recommended to use a virtual environment:"
        echo "  python3 -m venv vbridge-env"
        echo "  source vbridge-env/bin/activate  # On Windows: vbridge-env\\Scripts\\activate"
        echo ""
        read -p "Continue without virtual environment? (y/N): " -r
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Exiting. Please set up a virtual environment first."
            exit 1
        fi
    fi
    
    # Install dependencies
    if [[ -f "requirements.txt" ]]; then
        print_status "Installing from requirements.txt..."
        pip3 install -r requirements.txt
        print_success "Python dependencies installed successfully"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
    
    # Install VBridge in development mode
    print_status "Installing VBridge package in development mode..."
    pip3 install -e .
    print_success "VBridge package installed"
}

# Install Node.js dependencies
install_node_deps() {
    print_status "Installing Node.js dependencies..."
    
    if [[ -d "client" ]]; then
        cd client
        
        # Clean install
        if [[ -d "node_modules" ]]; then
            print_status "Cleaning existing node_modules..."
            rm -rf node_modules package-lock.json
        fi
        
        print_status "Running npm install..."
        npm install
        
        print_success "Node.js dependencies installed successfully"
        cd ..
    else
        print_error "client directory not found"
        exit 1
    fi
}

# Download sample data
download_sample_data() {
    print_status "Downloading MIMIC-III demo dataset..."
    
    if [[ ! -d "data" ]]; then
        mkdir data
    fi
    
    # Check if data already exists
    if [[ -d "data/physionet.org/files/mimiciii-demo/1.4" ]]; then
        print_warning "MIMIC-III demo data already exists"
        read -p "Re-download? (y/N): " -r
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Skipping data download"
            return
        fi
    fi
    
    # Download with wget or curl
    if command -v wget &> /dev/null; then
        print_status "Using wget to download data..."
        wget -r -N -c -np https://physionet.org/files/mimiciii-demo/1.4/ -P data/
    elif command -v curl &> /dev/null; then
        print_status "Using curl to download data..."
        mkdir -p data/physionet.org/files/mimiciii-demo/1.4/
        cd data/physionet.org/files/mimiciii-demo/1.4/
        curl -O https://physionet.org/files/mimiciii-demo/1.4/{ADMISSIONS.csv,CALLOUT.csv,CAREGIVERS.csv,CHARTEVENTS.csv,CPTEVENTS.csv,DATETIMEEVENTS.csv,DIAGNOSES_ICD.csv,DRGCODES.csv,D_CPT.csv,D_ICD_DIAGNOSES.csv,D_ICD_PROCEDURES.csv,D_ITEMS.csv,D_LABITEMS.csv,ICUSTAYS.csv,INPUTEVENTS_CV.csv,INPUTEVENTS_MV.csv,LABEVENTS.csv,MICROBIOLOGYEVENTS.csv,NOTEEVENTS.csv,OUTPUTEVENTS.csv,PATIENTS.csv,PRESCRIPTIONS.csv,PROCEDURES_ICD.csv,SERVICES.csv,TRANSFERS.csv}
        cd ../../../../..
    else
        print_error "Neither wget nor curl found. Please install one of them or download data manually."
        print_status "Manual download: Visit https://physionet.org/content/mimiciii-demo/1.4/"
        print_status "Extract to: data/physionet.org/files/mimiciii-demo/1.4/"
        return
    fi
    
    # Verify data download
    if [[ -f "data/physionet.org/files/mimiciii-demo/1.4/PATIENTS.csv" ]]; then
        print_success "MIMIC-III demo dataset downloaded successfully"
    else
        print_error "Data download failed. Please download manually."
    fi
}

# Run tests
run_tests() {
    print_status "Running basic tests..."
    
    # Test Python import
    python3 -c "
import sys
try:
    import vbridge
    print('✓ VBridge import successful')
except ImportError as e:
    print(f'✗ VBridge import failed: {e}')
    sys.exit(1)

try:
    import pandas, numpy, sklearn, featuretools, xgboost, shap, flask
    print('✓ All major dependencies imported successfully')
except ImportError as e:
    print(f'✗ Dependency import failed: {e}')
    sys.exit(1)
" || exit 1
    
    print_success "Python environment tests passed"
}

# Main installation
main() {
    echo ""
    print_status "Starting VBridge Modernized installation..."
    echo ""
    
    # Check if we're in the right directory
    if [[ ! -f "setup.py" ]] || [[ ! -d "vbridge" ]]; then
        print_error "Please run this script from the VBridge root directory"
        exit 1
    fi
    
    check_requirements
    echo ""
    
    install_python_deps
    echo ""
    
    install_node_deps
    echo ""
    
    download_sample_data
    echo ""
    
    run_tests
    echo ""
    
    print_success "🎉 Installation completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Start the Python API server:"
    echo "   python vbridge/router/app.py"
    echo ""
    echo "2. In another terminal, start the React frontend:"
    echo "   cd client && npm start"
    echo ""
    echo "3. Open your browser to:"
    echo "   - Frontend: http://localhost:3000"
    echo "   - API docs: http://localhost:7777/apidocs"
    echo ""
    print_status "Happy analyzing! 🔬"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "VBridge Modernized Installation Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --python-only  Install only Python dependencies"
        echo "  --node-only    Install only Node.js dependencies"
        echo "  --no-data      Skip data download"
        echo ""
        exit 0
        ;;
    --python-only)
        check_requirements
        install_python_deps
        run_tests
        ;;
    --node-only)
        check_requirements
        install_node_deps
        ;;
    --no-data)
        check_requirements
        install_python_deps
        install_node_deps
        run_tests
        ;;
    *)
        main
        ;;
esac 