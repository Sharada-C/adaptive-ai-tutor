import { useCallback, useEffect, useState } from "react";
import * as api from "../api";

// Admin-only: see every account, change roles, deactivate accounts and
// reset passwords. The server enforces all of this; hiding the page from
// other roles is only a convenience.

const ROLES = [
  { value: "student", label: "Student" },
  { value: "instructor", label: "Instructor" },
  { value: "admin", label: "Admin" },
];

export default function AdminScreen({ currentUserId, onBack }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [resetId, setResetId] = useState(null);
  const [newPassword, setNewPassword] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setUsers(await api.listUsers());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const change = async (user, changes) => {
    try {
      setBusyId(user.id);
      setError("");

      const updated = await api.updateUser(user.id, changes);

      setUsers((list) => list.map((u) => (u.id === user.id ? updated : u)));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const savePassword = async (user) => {
    await change(user, { password: newPassword });
    setResetId(null);
    setNewPassword("");
  };

  return (
    <main className="main-content">
      <section className="setup-card admin-card">
        <div className="card-header">
          <div>
            <h3>Manage users</h3>
            <p>
              Students can learn. Instructors can also add courses and study
              material and view learners' progress. Admins can also manage
              accounts.
            </p>
          </div>
        </div>

        {error && (
          <div className="error-message" role="alert">
            {error}
          </div>
        )}

        {loading ? (
          <div className="loading-message">Loading users...</div>
        ) : (
          <table className="user-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>

            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    {user.username}
                    {user.id === currentUserId && " (you)"}
                    {!user.has_password && (
                      <small className="user-note"> no password set</small>
                    )}
                  </td>

                  <td>
                    <select
                      aria-label={`Role for ${user.username}`}
                      value={user.role}
                      disabled={busyId === user.id}
                      onChange={(event) =>
                        change(user, { role: event.target.value })
                      }
                    >
                      {ROLES.map((role) => (
                        <option key={role.value} value={role.value}>
                          {role.label}
                        </option>
                      ))}
                    </select>
                  </td>

                  <td>{user.is_active ? "Active" : "Deactivated"}</td>

                  <td className="user-actions">
                    {resetId === user.id ? (
                      <>
                        <input
                          type="password"
                          aria-label={`New password for ${user.username}`}
                          className="text-input"
                          value={newPassword}
                          onChange={(event) =>
                            setNewPassword(event.target.value)
                          }
                          placeholder="New password"
                        />

                        <button
                          type="button"
                          className="nav-button"
                          disabled={
                            newPassword.length < 8 || busyId === user.id
                          }
                          onClick={() => savePassword(user)}
                        >
                          Save
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="nav-button"
                        onClick={() => {
                          setResetId(user.id);
                          setNewPassword("");
                        }}
                      >
                        Set password
                      </button>
                    )}

                    <button
                      type="button"
                      className="nav-button"
                      disabled={busyId === user.id}
                      onClick={() =>
                        change(user, { is_active: !user.is_active })
                      }
                    >
                      {user.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <button
          type="button"
          className="skip-diagnostic-button"
          onClick={onBack}
        >
          Back to learning
        </button>
      </section>
    </main>
  );
}
