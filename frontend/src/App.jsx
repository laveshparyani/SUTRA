import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth.jsx";
import { Layout } from "./components/Layout.jsx";
import { Alerts } from "./pages/Alerts.jsx";
import { Atlas } from "./pages/Atlas.jsx";
import { Dashboard } from "./pages/Dashboard.jsx";
import { Detections } from "./pages/Detections.jsx";
import { Login } from "./pages/Login.jsx";
import { Registry } from "./pages/Registry.jsx";
import { Trace } from "./pages/Trace.jsx";
import { Wall } from "./pages/Wall.jsx";
import { Watchlist } from "./pages/Watchlist.jsx";
import { AlertProvider } from "./ws.jsx";

function Protected({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="*"
            element={
              <Protected>
                <AlertProvider>
                  <Layout>
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/wall" element={<Wall />} />
                      <Route path="/trace" element={<Trace />} />
                      <Route path="/detections" element={<Detections />} />
                      <Route path="/alerts" element={<Alerts />} />
                      <Route path="/registry" element={<Registry />} />
                      <Route path="/atlas" element={<Atlas />} />
                      <Route path="/watchlist" element={<Watchlist />} />
                    </Routes>
                  </Layout>
                </AlertProvider>
              </Protected>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
