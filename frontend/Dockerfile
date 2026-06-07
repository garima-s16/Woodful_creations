FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY . .

# Build Next.js (optional for dev, remove for dev-only)
# RUN npm run build

# Expose port
EXPOSE 3000

# Run development server
CMD ["npm", "run", "dev"]
