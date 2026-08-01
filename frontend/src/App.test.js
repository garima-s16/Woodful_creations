import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import App from './App';

jest.mock('axios');

describe('App', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows backend connection details when the health check succeeds', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        service: 'Woodful Creations API',
        version: '1.0.0',
      },
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/API Status: CONNECTED/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Woodful Creations API/i)).toBeInTheDocument();
  });

  it('shows an offline message when the health check fails', async () => {
    axios.get.mockRejectedValueOnce(new Error('offline'));
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/API Status: DISCONNECTED/i)).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Backend unavailable\. Start the API server and refresh/i)
    ).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });
});
