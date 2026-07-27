import { FormEvent, useState } from "react";

interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  department_id: string;
}

export function LoginPage({
  error,
  onLogin,
  onRegister
}: {
  error: string;
  onLogin: (email: string, password: string) => void;
  onRegister: (payload: RegisterPayload) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("新员工");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("123456");
  const [departmentId, setDepartmentId] = useState("dept-product");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (mode === "login") {
      onLogin(email.trim(), password);
      return;
    }
    onRegister({ name: name.trim(), email: email.trim(), password, department_id: departmentId });
  }

  return (
    <main className="loginShell">
      <section className="loginPanel">
        <div className="brand loginBrand">
          <div className="brandMark">K</div>
          <div>
            <strong>知识平台</strong>
            <span>企业内部知识库与文档协作</span>
          </div>
        </div>
        <div className="segmented authSwitch">
          <button className={mode === "login" ? "selected" : ""} onClick={() => setMode("login")}>
            登录
          </button>
          <button className={mode === "register" ? "selected" : ""} onClick={() => setMode("register")}>
            注册
          </button>
        </div>
        <form className="loginForm" onSubmit={submit}>
          {mode === "register" ? (
            <>
              <label>
                <span>姓名</span>
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
              <label>
                <span>部门</span>
                <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
                  <option value="dept-product">产品部</option>
                  <option value="dept-tech">技术部</option>
                  <option value="dept-hr">人事部</option>
                  <option value="dept-finance">财务部</option>
                </select>
              </label>
            </>
          ) : null}
          <label>
            <span>邮箱</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            <span>密码</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <p className="formError">{error}</p> : null}
          <button className="primaryAction" type="submit">
            {mode === "login" ? "登录" : "注册并进入"}
          </button>
        </form>
        <p className="loginHint">演示账号：admin@example.com / 123456</p>
      </section>
    </main>
  );
}
