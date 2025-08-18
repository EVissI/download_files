module.exports = {
    apps: [
        {
            name: "nard-app",
            script: "npm",
            args: "start",
            cwd: "/var/www/nards",
            env: {
                NODE_ENV: "production"
            }
        }
    ]
};
