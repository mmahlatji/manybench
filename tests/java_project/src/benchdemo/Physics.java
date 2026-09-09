package benchdemo;

import java.util.List;

public class Physics {

    // @bench physics-step
    // @bench-param n = [1000, 10000]
    public static void step(int n) {
        int x = 0;
        for (int i = 0; i < n; i++) x += i;
    }

    // @bench check-collisions
    // @bench-param particles = [1000, 10000]
    // @bench-param subSteps = [1, 2]
    // @bench-fixture createParticles
    public static void checkCollisions(List<Integer> particles, int subSteps) {
        int x = 0;
        for (int i = 0; i < particles.size(); i++) x += particles.get(i) * subSteps;
    }

    // @bench-fixture createParticles
    public static List<Integer> createParticles(int particles) {
        List<Integer> list = new java.util.ArrayList<>(particles);
        for (int i = 0; i < particles; i++) list.add(i);
        return list;
    }
}
