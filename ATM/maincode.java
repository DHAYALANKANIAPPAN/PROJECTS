import java.sql.*;
import java.util.Scanner;
import java.io.*;

public class App {
    private static final String URL = "jdbc:mysql://localhost:3306/dhaya";
    private static final String USERNAME = "root";
    private static final String PASSWORD = "admin";

    public static void main(String[] args) {
        Scanner d = new Scanner(System.in);
        int pin_no;

        System.out.println("Enter your PIN:");
        int enteredPin = d.nextInt();

        try (Connection conn = DriverManager.getConnection(URL, USERNAME, PASSWORD)) {
            PreparedStatement p = conn.prepareStatement("SELECT   *FROM bank WHERE pin_no = ?");
            p.setInt(1, enteredPin);
            ResultSet rs = p.executeQuery();

            if (rs.next()) {
                pin_no = rs.getInt("pin_no");
                System.out.println("Login successful!");

                int choice;
                do {
                    System.out.println("\nEnter operation:");
                    System.out.println("1. Deposit\n2. Withdraw\n3. View Balance\n4.pinchange");
                    choice = d.nextInt();

                    switch (choice) {
                        case 1:
                            System.out.println("Enter amount to deposit:");
                            int depAmount = d.nextInt();
                            Deposit(depAmount, pin_no);

                            break;
                        case 2:
                            System.out.println("Enter amount to withdraw:");
                            int withAmount = d.nextInt();
                            Withdraw(withAmount, pin_no);

                            break;
                        case 3:
                            int balance = ShowBalance(pin_no);
                            System.out.println("Your balance: " + balance);
                            break;
                        case 4:
                            System.out.println("enter a newpin");
                            int newpin = d.nextInt();
                            pinchange(newpin, pin_no);
                            break;
                        default:
                            System.out.println("Invalid choice.");
                    }
                } while (choice != 5);
            } else {
                System.out.println("Invalid PIN.");
            }
        } catch (SQLException e) {
            System.out.println("Error: " + e.getMessage());
        }
    }

    public static void Deposit(int amount, int pin_no) {
        String sql = "UPDATE bank SET balance = balance + ? WHERE pin_no = ?";
        try (Connection conn = DriverManager.getConnection(URL, USERNAME, PASSWORD);
                PreparedStatement p = conn.prepareStatement(sql)) {

            p.setInt(1, amount);
            p.setInt(2, pin_no);
            int rows = p.executeUpdate();
            System.out.println("Deposit successful!");
            int newBalance = ShowBalance(pin_no);
            generateReceipt("deposit", amount, newBalance);

        } catch (SQLException e) {
            System.out.println("Error in deposit: " + e.getMessage());
        }
    }

    public static void Withdraw(int amount, int pin_no) {
        String sql = "UPDATE bank SET balance = balance - ? WHERE pin_no = ? AND balance >= ?";
        try (Connection conn = DriverManager.getConnection(URL, USERNAME, PASSWORD);
                PreparedStatement p = conn.prepareStatement(sql)) {
            p.setInt(1, amount);
            p.setInt(2, pin_no);
            p.setInt(3, amount);
            int rows = p.executeUpdate();
            if (rows > 0) {
                System.out.println("Withdraw successful!");
                int newBalance = ShowBalance(pin_no);
                generateReceipt("Withdraw", amount, newBalance);
            } else {
                System.out.println("Insufficient balance!");
            }
        } catch (SQLException e) {
            System.out.println("Error in withdraw: " + e.getMessage());
        }
    }

    public static int ShowBalance(int pin_no) {
        String sql = "SELECT balance FROM bank WHERE pin_no = ?";
        try (Connection conn = DriverManager.getConnection(URL, USERNAME, PASSWORD);
                PreparedStatement p = conn.prepareStatement(sql)) {

            p.setInt(1, pin_no);
            ResultSet rs = p.executeQuery();
            if (rs.next()) {
                return rs.getInt("balance");
            }

        } catch (SQLException e) {
            System.out.println("Error getting balance: " + e.getMessage());
        }
        return 0;
    }

    public static void pinchange(int newpin, int pin_no) {
        String sql = "UPDATE bank SET pin_no= ? WHERE pin_no = ? ";
        try (Connection conn = DriverManager.getConnection(URL, USERNAME, PASSWORD);
                PreparedStatement p = conn.prepareStatement(sql)) {

            p.setInt(1, newpin);
            p.setInt(2, pin_no);
            int b = p.executeUpdate();
            if (b > 0)
                System.out.println("pin changed successful!");
            else
                System.out.println("Error occured!");
        } catch (SQLException e) {
            System.out.println("Error changing pin: " + e.getMessage());
        }

    }

    public static void generateReceipt(String type, int amount, int balance) {
        try {

            String fileName = "D:\\pro.txt";

            FileWriter writer = new FileWriter(fileName);
            writer.write("TRANSACTION RECEIPT \n");
            writer.write("Type       :" + type + "\n");
            writer.write("Amount     " + type + ":" + amount + "\n");
            writer.write("Balance    :" + balance + "\n");
            writer.close();

            BufferedReader reader = new BufferedReader(new FileReader(fileName));
            String line;

            while ((line = reader.readLine()) != null) {
                System.out.println(line);
            }
            reader.close();

        } catch (Exception e) {
            System.out.println(" Error writing receipt: " + e.getMessage());
        }
    }
}
