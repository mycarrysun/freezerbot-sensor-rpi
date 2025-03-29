<template>
  <div class="container">
    <div class="logo">
      <img src="/logo.png" alt="Freezerbot Logo">
    </div>
    <h1>Freezerbot Setup</h1>

    <SetupForm v-if="!setupComplete" @setup-completed="onSetupCompleted" />

    <div v-if="setupComplete" class="success">
      <div class="success-icon">✓</div>
      <h2>Setup Complete!</h2>
      <p>Your Freezerbot has been successfully configured and will restart in:</p>
      <div class="countdown">{{ countdown }}</div>
      <p>Once restarted, the device will connect to your WiFi network and begin monitoring your freezer temperature.</p>
      <p>You can now close this page and disconnect from the Freezerbot setup network.</p>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';
import SetupForm from './components/SetupForm.vue';

export default {
  components: {
    SetupForm
  },
  setup() {
    const setupComplete = ref(false);
    const countdown = ref(10);

    function onSetupCompleted() {
      setupComplete.value = true;

      const timer = setInterval(() => {
        countdown.value--;

        if (countdown.value <= 0) {
          clearInterval(timer);
        }
      }, 1000);
    }

    return {
      setupComplete,
      countdown,
      onSetupCompleted
    };
  }
}
</script>

<style>
body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 20px;
  background-color: #f5f5f5;
  color: #333;
}
.container {
  max-width: 500px;
  margin: 0 auto;
  background: white;
  padding: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.logo {
  text-align: center;
  margin-bottom: 20px;
}
.logo img {
  width: 180px;
}
h1 {
  text-align: center;
  color: #0066cc;
}
.success {
  text-align: center;
}
.success-icon {
  font-size: 60px;
  color: #4CAF50;
  margin-bottom: 20px;
}
.countdown {
  font-size: 24px;
  margin: 20px 0;
  font-weight: bold;
}
</style>