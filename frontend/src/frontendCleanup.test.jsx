import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import Navbar from './components/Navbar';
import PaymentsPage from './pages/PaymentsPage';

describe('frontend cleanup updates', () => {
  it('removes demo login content from the login page', () => {
    render(
      <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <LoginPage onLogin={jest.fn()} />
      </MemoryRouter>
    );

    expect(screen.queryByText(/demo login/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/test credentials/i)).not.toBeInTheDocument();
  });

  it('adds an accessible label to the navigation toggle', () => {
    render(
      <MemoryRouter future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <Navbar
          isSidebarOpen={false}
          onLogout={jest.fn()}
          toggleSidebar={jest.fn()}
          user={{ name: 'Woodful User', email: 'user@example.com', role: 'user' }}
        />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('button', { name: /toggle navigation menu/i })
    ).toBeInTheDocument();
  });

  it('uses generic master-user copy in the payments page', () => {
    render(<PaymentsPage />);

    expect(screen.getByText(/authorized master users/i)).toBeInTheDocument();
    expect(screen.queryByText(/nikhil|garima/i)).not.toBeInTheDocument();
  });
});
