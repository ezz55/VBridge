#!/bin/bash

# VBridge Modernized - Quick Start Script
# Starts both Python API server and React frontend

echo "🚀 Starting VBridge Modernized"
echo "==============================="

# Check if we're in the right directory
if [[ ! -f "setup.py" ]] || [[ ! -d "vbridge" ]]; then
    echo "❌ Error: Please run this script from the VBridge root directory"
    exit 1
fi

# Check if data exists
if [[ ! -d "data/physionet.org/files/mimiciii-demo/1.4" ]]; then
    echo "⚠️  Warning: MIMIC-III demo data not found"
    echo "Run './install.sh' to download the data first"
    echo ""
fi

# Function to kill background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down VBridge..."
    if [[ ! -z "$API_PID" ]]; then
        kill $API_PID 2>/dev/null
        echo "   ✓ API server stopped"
    fi
    if [[ ! -z "$FRONTEND_PID" ]]; then
        kill $FRONTEND_PID 2>/dev/null
        echo "   ✓ Frontend server stopped"
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "🐍 Starting Python API server..."
python vbridge/router/app.py &
API_PID=$!

# Wait a moment for the API server to start
sleep 3

# Check if API server is running
if kill -0 $API_PID 2>/dev/null; then
    echo "   ✓ API server running at http://localhost:7777"
    echo "   📖 API docs: http://localhost:7777/apidocs"
else
    echo "   ❌ API server failed to start"
    exit 1
fi

echo ""
echo "⚛️  Starting React frontend..."
cd client
npm start &
FRONTEND_PID=$!
cd ..

# Wait a moment for the frontend to start
sleep 5

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "   ✓ Frontend running at http://localhost:3000"
else
    echo "   ❌ Frontend failed to start"
    kill $API_PID 2>/dev/null
    exit 1
fi

echo ""
echo "🎉 VBridge is now running!"
echo ""
echo "Access points:"
echo "   • Main Interface: http://localhost:3000"
echo "   • API Server: http://localhost:7777"
echo "   • API Documentation: http://localhost:7777/apidocs"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for both processes
wait $API_PID $FRONTEND_PID 