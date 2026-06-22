import React, { useState } from "react";
import axios from "axios";
import { Lock, User, AlertCircle, Loader2, Brain } from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("Vui lòng điền đầy đủ thông tin.");
      return;
    }

    setLoading(true);
    setError("");
    setSuccessMsg("");

    try {
      if (isRegisterMode) {
        // Gọi API đăng ký
        const response = await axios.post(`${API_BASE_URL}/auth/register`, {
          username: username.trim(),
          password: password.trim(),
        });
        if (response.data.status === "success") {
          setSuccessMsg("Đăng ký thành công! Hãy đăng nhập bằng tài khoản mới.");
          setIsRegisterMode(false);
          setPassword("");
        }
      } else {
        // Gọi API đăng nhập
        const response = await axios.post(`${API_BASE_URL}/auth/login`, {
          username: username.trim(),
          password: password.trim(),
        });
        const { access_token } = response.data;
        localStorage.setItem("token", access_token);
        onLogin();
      }
    } catch (err) {
      console.error(err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Có lỗi xảy ra, vui lòng kết nối lại máy chủ.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-full opacity-20 pointer-events-none">
        <div className="absolute top-[20%] left-[10%] w-[40%] h-[40%] bg-blue-600 rounded-full blur-[130px]"></div>
        <div className="absolute bottom-[20%] right-[10%] w-[30%] h-[30%] bg-indigo-600 rounded-full blur-[110px]"></div>
      </div>

      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-500/10 text-blue-400 mb-4">
            <Brain className="w-10 h-10" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-wide">
            {isRegisterMode ? "Tạo Tài Khoản Mới" : "Đăng Nhập Hệ Thống"}
          </h1>
          <p className="text-slate-400 text-sm mt-2">
            {isRegisterMode
              ? "Đăng ký thành viên để bắt đầu sử dụng"
              : "Ứng dụng AI vào chuyển đổi số & Định giá tài sản"}
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm mb-6">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {successMsg && (
          <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm mb-6">
            <AlertCircle className="w-4 h-4 shrink-0 text-emerald-400" />
            <p>{successMsg}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Tên đăng nhập
            </label>
            <div className="relative flex items-center bg-slate-950 border border-slate-800 focus-within:border-blue-500/50 rounded-xl px-4 py-3 transition-colors">
              <User className="w-5 h-5 text-slate-500" />
              <input
                type="text"
                placeholder="Tên đăng nhập..."
                className="w-full bg-transparent border-none text-slate-100 pl-3 focus:outline-none placeholder:text-slate-600 text-sm"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Mật khẩu
            </label>
            <div className="relative flex items-center bg-slate-950 border border-slate-800 focus-within:border-blue-500/50 rounded-xl px-4 py-3 transition-colors">
              <Lock className="w-5 h-5 text-slate-500" />
              <input
                type="password"
                placeholder="Mật khẩu..."
                className="w-full bg-transparent border-none text-slate-100 pl-3 focus:outline-none placeholder:text-slate-600 text-sm"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-blue-500/20 active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed text-sm"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {isRegisterMode ? "Đang đăng ký..." : "Đang đăng nhập..."}
              </>
            ) : isRegisterMode ? (
              "Đăng ký"
            ) : (
              "Đăng nhập"
            )}
          </button>
        </form>

        <div className="text-center mt-6">
          <button
            type="button"
            className="text-xs text-blue-400 hover:underline"
            onClick={() => {
              setIsRegisterMode(!isRegisterMode);
              setError("");
              setSuccessMsg("");
            }}
          >
            {isRegisterMode
              ? "Đã có tài khoản? Đăng nhập ngay"
              : "Chưa có tài khoản? Tạo tài khoản mới"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
