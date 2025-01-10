// src/components/Dashboard.tsx
import { useEffect, useState } from 'react';
import { getToken, logout } from '../services/Auth';
import axios from 'axios';

function Dashboard() {
  const [data, setData] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const token = getToken();
        if (!token) throw new Error('Token não encontrado');

        const response = await axios.get('http://localhost:3333', {
          headers: { Authorization: `Bearer ${token}` },
        });
        setData(response.data.message);
      } catch (err) {
        setError('Erro ao carregar os dados.');
      }
    };

    fetchData();
  }, []);

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <div>
      <h1>Dashboard</h1>
      {error ? (
        <p style={{ color: 'red' }}>{error}</p>
      ) : data ? (
        <p>{data}</p>
      ) : (
        <p>Carregando...</p>
      )}
      <button onClick={handleLogout}>Sair</button>
    </div>
  );
}

export default Dashboard;
