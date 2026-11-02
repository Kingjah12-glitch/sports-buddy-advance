// Static mode: the website reads only the saved files in ./data (built every morning by the
// GitHub Action). Visitors can never cause a call to API-Football.
// To use a live API instead, put your Render address here, e.g.
//   window.SB_CONFIG = { apiBase: "https://YOUR-SERVICE.onrender.com", dataBase: "data" };
window.SB_CONFIG = { apiBase: "", dataBase: "data" };
