import { Navigate, Route, Routes } from "react-router-dom";
import { isLoggedIn } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Attendance from "./pages/Attendance";
import PayrollApprovals from "./pages/PayrollApprovals";
import Dpr from "./pages/Dpr";
import Store from "./pages/Store";
import Expenses from "./pages/Expenses";

function PrivateRoute({ children }) {
  if (!isLoggedIn()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Home />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="payroll" element={<PayrollApprovals />} />
        <Route path="dpr" element={<Dpr />} />
        <Route path="store" element={<Store />} />
        <Route path="expenses" element={<Expenses />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
